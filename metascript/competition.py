#!/usr/bin/env python3
#
# Copyright 1996-2022 Cyberbotics Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import datetime, timezone
import json
import os
import re
import requests
import shutil
import subprocess
import sys
from .animation import record_animations, TMP_ANIMATION_DIRECTORY
from .utils import git, webots_cloud

# YAML booleans are converted to strings by GitHub composite Actions, so we need to convert them back to booleans
UPLOAD_PERFORMANCE = re.search(r"^(?:y|Y|yes|Yes|YES|true|True|TRUE|on|On|ON)$", os.environ['UPLOAD_PERFORMANCE'])
OPPONENT_REPO_NAME = os.environ['OPPONENT_REPO_NAME']


class Participant:
    def __init__(self, id, repository, private, opponent=False):
        self.id = id
        self.repository = repository
        self.private = private
        self.controller_path = os.path.join('controllers', id)
        repo = 'https://{}:{}@github.com/{}'.format('Competition_Evaluator', os.environ['REPO_TOKEN'], self.repository)
        if git.clone(repo, self.controller_path):
            self.data = _load_json(os.path.join(self.controller_path, 'controllers', 'participant', 'participant.json'))
            if self.data:  # sanity checks
                url = f'https://github.com/{repository}/blob/main/controllers/participant/participant.json'
                message = '::warning ::' if opponent else '::error ::'
                if 'name' not in self.data:
                    print(f'{message}Missing name in {url}')
                    if not opponent:
                        sys.exit(1)
                if 'description' not in self.data:
                    print(f'{message}Missing description in {url}')
                    if not opponent:
                        sys.exit(1)
                if 'country' not in self.data:
                    print(f'{message}Missing country code in {url}')
                    if not opponent:
                        sys.exit(1)
                else:
                    country = self.data['country']
                    if country != 'demo' and len(country) != 2:
                        print(f'{message}Bad country code in {url} (you should set a two-letter country code, see '
                              + 'https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2 for details)')
                        if not opponent:
                            sys.exit(1)
                if 'programming' not in self.data:
                    self.data['programming'] = 'Python'
        else:
            self.data = None
        if opponent:
            self.log = None
        else:
            self.log = os.environ['LOG_URL']


def competition(config):
    # Determine if GPU acceleration is available (typically on a self-hosted runner)
    if shutil.which('nvidia-docker'):
        version = subprocess.check_output(['nvidia-docker', '-v']).decode('utf-8').strip().split(' ')[2][:-1]
        print(f'GPU detected on runner machine: nvidia-docker version {version}')
        subprocess.check_output(['xhost', '+local:root'])
        gpu = True
    else:
        print('No GPU detected, running on CPU')
        gpu = False

    git.init()

    response = requests.get(
        f'https://webots.cloud/storage/competition/{os.environ["GITHUB_REPOSITORY"]}/participants.json')
    open("participants.json", "wb").write(response.content)

    # Parse input participant
    participant = _get_participant()
    if participant.data is None:
        print('::error ::Cannot parse '
              + f'https://github.com/{participant.repository}/blob/main/controllers/participant/participant.json, '
              + 'please provide or fix this file.')
        sys.exit(1)
    performance = None
    animator_controller_destination_path = _copy_animator_files()
    failure = False
    if config['world']['metric'] == 'ranking':  # run a bubble sort ranking
        while True:
            opponent = _get_opponent(participant)
            if opponent is None:  # we reached the top of the ranking
                if OPPONENT_REPO_NAME:
                    print(f'::error ::Specified opponent was not found: {OPPONENT_REPO_NAME}')
                    break
                if performance is None:  # number 1 was modified, so no performance evaluation was run
                    # we still need to update the participant data in case they were modified
                    participants = _load_participants()
                    if len(participants) == 0:  # number 1 is the first one to be submitted
                        p = {}
                        _update_participant(p, participant, 1)
                        participants['participants'].append(p)
                    else:  # number 1 was updated
                        for p in participants['participants']:
                            if p['id'] == participant.id:
                                _update_participant(p, participant, 1)
                    _save_participants(participants)
                break
            performance = int(record_animations(gpu, config, participant.controller_path, participant.data['name'],
                                                opponent.controller_path, opponent.data['name'],
                                                True if performance is None else False))
            if performance == -1:
                failure = True
            elif performance == 1:
                opponent.log = os.environ['LOG_URL']
            if OPPONENT_REPO_NAME:
                _update_friendly_game(performance, participant, opponent)
            else:
                _update_ranking(performance, participant, opponent)
            _update_animation_files(participant if OPPONENT_REPO_NAME or performance != 1 else opponent)
            shutil.rmtree(opponent.controller_path)
            if performance != 1 or OPPONENT_REPO_NAME:  # draw, loose or friendly game: stop evaluations
                break
    else:  # run a simple performance evaluation
        performance = record_animations(gpu, config, participant.controller_path, participant.data['name'])
        higher_is_better = config['world']['higher-is-better'] if 'higher-is-better' in config['world'] else True
        _update_performance(performance, participant, higher_is_better)
        _update_animation_files(participant)
    shutil.rmtree(participant.controller_path)
    shutil.rmtree(animator_controller_destination_path)

    # cleanup docker containers, images and networks not used in the last 30 days
    subprocess.check_output(['docker', 'system', 'prune', '--force', '--filter', 'until=720h'])

    if UPLOAD_PERFORMANCE:
        webots_cloud.upload_file(os.environ['GITHUB_REPOSITORY'], os.environ['REPO_TOKEN'], 'participants.json', 'participants')
        if os.path.isdir('storage'):
            os.chdir('storage')
            for f in os.listdir('.'):
                if f == '.' or f == '..':
                    continue
                filename = os.path.join(f, 'animation.json')
                webots_cloud.upload_file(os.environ['GITHUB_REPOSITORY'], os.environ['REPO_TOKEN'], filename, 'animation')
            os.chdir('..')
    if failure:
        sys.exit(1)


def _get_opponent(participant):
    participants = _load_participants()
    if len(participants['participants']) == 0:
        p = {}
        _update_participant(p, participant, 1)
        participants['participants'].append(p)
        _save_participants(participants)
        print(f'Welcome {participant.repository}, you are the first participant there')
        return None

    if OPPONENT_REPO_NAME:
        for p in participants['participants']:
            if p['repository'] == OPPONENT_REPO_NAME:
                opponent = Participant(p['id'], p['repository'], p['private'], True)
                if opponent.data is not None:
                    return opponent
        return None

    i = 0
    found = False
    for p in participants['participants']:
        if p['id'] == participant.id:
            found = True
            break
        i += 1
    if i == 0 and found:
        print(f'{participant.repository} is number 1 in the ranking')
        return None
    if not found:
        print(f'Welcome {participant.repository} and good luck for the competition')
    while i > 0:
        o = participants['participants'][i - 1]
        print(f'Cloning \033[34mopponent\033[0m repository: {o["repository"]}')
        opponent = Participant(o['id'], o['repository'], o['private'], True)
        if opponent.data is not None:
            return opponent
        print(f'{o["repository"]} is not participating any more, removing it')
        del participants['participants'][i - 1]
        max = len(participants['participants'])
        j = i
        while j < max:  # update performance of controllers below the one deleted
            participants['participants'][j]['performance'] -= 1
            j += 1
        _save_participants(participants)
        i -= 1
    print(f'All opponents have left, {participant.repository} becomes number 1')
    return None


def _get_participant():
    print(f'Cloning \033[31mparticipant\033[0m repository: {os.environ["PARTICIPANT_REPO_NAME"]}')
    participant = Participant(
        os.environ['PARTICIPANT_REPO_ID'],
        os.environ['PARTICIPANT_REPO_NAME'],
        os.environ['PARTICIPANT_REPO_PRIVATE'] == 'true')
    return participant


def _copy_animator_files():
    animator_controller_source = os.path.join('metascript', 'animator')
    animator_controller_destination = os.path.join('controllers', 'animator')
    shutil.copytree(animator_controller_source, animator_controller_destination)
    return animator_controller_destination


def _update_participant(p, participant, performance=None):
    p['id'] = participant.id
    p['repository'] = participant.repository
    p['private'] = participant.private
    p['name'] = participant.data['name']
    p['description'] = participant.data['description']
    p['country'] = participant.data['country']
    p['programming'] = participant.data['programming']
    if 'friend' in participant.data:
        p['friend'] = { 'name': participant.data['friend']['name'], 'result': participant.data['friend']['result'] }
    if participant.log is not None:
        p['log'] = participant.log
        p['date'] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if performance is not None:
        p['performance'] = performance


def _update_performance(performance, participant, higher_is_better):
    # change the requested participant's performance and update list order
    participants = _load_participants()
    i = 0
    found = False
    for p in participants['participants']:
        if p['id'] == participant.id:
            found = True
            break
        i += 1
    np = participants['participants'].pop(i) if found else {}
    _update_participant(np, participant, performance)
    i = 0
    for p in participants['participants']:
        if higher_is_better and performance > p['performance']:
            break
        elif not higher_is_better and performance < p['performance']:
            break
        i += 1
    participants['participants'].insert(i, np)
    _save_participants(participants)


def _update_friendly_game(performance, participant, opponent):
    # set result and opponent name for a friendly game
    participants = _load_participants()
    opponent_name = None
    for p in participants['participants']:
        if p['id'] == opponent.id:
            opponent_name = p['name']
            break
    if opponent_name is None:
        print('::error ::Could not find opponent in a friendly game')
        return
    for p in participants['participants']:
        if p['id'] == participant.id:
            p['friend'] = {'name': opponent_name, 'result': 'W' if performance == 1 else 'L'}
            break
    _save_participants(participants)


def _update_ranking(performance, participant, opponent):
    # insert participant if new, and swap winning participant with opponent
    participants = _load_participants()
    found_participant = False
    found_opponent = False
    for p in participants['participants']:
        if p['id'] == opponent.id:
            found_opponent = p
            if found_participant:
                break
        elif p['id'] == participant.id:
            found_participant = p
            if found_opponent:
                break
    if not found_opponent:
        print('::error ::Missing opponent in participants.json')
        sys.exit(1)
    count = len(participants['participants']) + 1
    if performance != 1:  # participant lost
        if found_participant:  # nothing to change, however, the participant.json data may have changed
            _update_participant(found_participant, participant)
            _save_participants(participants)
            return
        # we need to add the participant at the bottom of the list
        p = {}
        _update_participant(p, participant, count)
        participants['participants'].append(p)
    else:
        if found_participant:  # swap
            rank = found_opponent['performance']
            _update_participant(found_opponent, participant, rank)
            _update_participant(found_participant, opponent, rank + 1)
        else:  # insert participant at last but one position, move opponent to last position
            if found_opponent['performance'] != count - 1:
                print('::error ::Opponent should be ranked last in participants.json '
                      + f'({found_opponent["performance"]} != {count - 1})')
                sys.exit(1)
            _update_participant(found_opponent, opponent, count)
            p = {}
            _update_participant(p, participant, count - 1)
            participants['participants'].insert(count - 2, p)
    _save_participants(participants)


def _load_participants():
    participants = _load_json('participants.json')
    if participants is None:
        participants = {'participants': []}
    return participants


def _save_participants(participants):
    _save_json('participants.json', participants)


def _load_json(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, encoding='utf-8') as f:
        return json.load(f)


def _save_json(filename, object):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(object, f, ensure_ascii=False, indent=2)


def _update_animation_files(participant):
    folder = os.path.join('storage', ('f' if OPPONENT_REPO_NAME else '') + participant.id)
    os.makedirs(folder)
    shutil.copy(os.path.join(TMP_ANIMATION_DIRECTORY, 'animation.json'), os.path.join(folder, 'animation.json'))
    shutil.rmtree(TMP_ANIMATION_DIRECTORY)
    return
