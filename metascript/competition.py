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
import shutil
import subprocess
import sys
from pathlib import Path
from .animation import record_animations, cleanup_containers, TMP_ANIMATION_DIRECTORY
from .utils import git

ALLOW_PUSH = os.getenv('INPUT_ALLOW_PUSH', False)


class Participant:
    def __init__(self, id, repository, private, opponent=False):
        self.id = id
        self.repository = repository
        self.private = private
        self.controller_path = os.path.join('controllers', id)
        repo = 'https://{}:{}@github.com/{}'.format('Competition_Evaluator', os.environ['INPUT_REPO_TOKEN'], self.repository)
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
                elif 'country' not in self.data:
                    print(f'{message}Missing country code in {url}')
                    if not opponent:
                        sys.exit(1)
                else:
                    country = self.data['country']
                    if len(country) != 2:
                        print(f'{message}Bad country code in {url}')
                        if not opponent:
                            sys.exit(1)
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
        print(f'::notice ::GPU detected on runner machine: nvidia-docker version {version}')
        subprocess.check_output(['xhost', '+local:root'])
        gpu = True
    else:
        print('::notice ::No GPU detected, running on CPU')
        gpu = False

    git.init()

    # Parse input participant
    participant = _get_participant()
    if participant.data is None:
        print(f'::error ::Cannot parse https://github.com/{participant.repository}/blob/main/controllers/participant/participant.json, please provide or fix this file.')
        sys.exit(1)
    performance = None
    animator_controller_destination_path = _copy_animator_files()
    failure = False
    if config['world']['metric'] == 'ranking':  # run a bubble sort ranking
        while True:
            opponent = _get_opponent(participant)
            if opponent is None:  # we reached the top of the ranking
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
                                                opponent.controller_path, opponent.data['name'], True if performance is None else False))
            if performance == -1:
                failure = True
                performance = 0
            _update_ranking(performance, participant, opponent)
            _update_animation_files(opponent if performance == 1 else participant)
            _remove_directory(opponent.controller_path)
            if performance != 1:  # draw or loose, stopping duals
                break
    else:  # run a simple performance evaluation
        performance = record_animations(gpu, config, participant.controller_path, participant.data['name'])
        higher_is_better = config['world']['higher-is-better'] if 'higher-is-better' in config['world'] else True
        _update_performance(performance, participant, higher_is_better)
        _update_animation_files(participant)
    _remove_directory(participant.controller_path)
    _remove_directory(animator_controller_destination_path)

    cleanup_containers()
    # cleanup docker containers, images, networks and volumes not used in the last 2.5 days
    subprocess.check_output(['docker', 'system', 'prune', '--force', '--filter', 'until=60h'])
    subprocess.check_output(['docker', 'volume', 'prune', '--force'])

    if ALLOW_PUSH:
        git.push(message='record and update competition animations')
    
    if failure:
        sys.exit(1)


def _get_opponent(participant):
    participants = _load_participants()
    if len(participants['participants']) == 0:
        p = {}
        _update_participant(p, participant, 1)
        participants['participants'].append(p)
        _save_participants(participants)
        print(f'::notice ::Welcome {participant.repository}, you are the first participant there')
        return None

    i = 0
    found = False
    for p in participants['participants']:
        if p['id'] == participant.id:
            found = True
            break
        i += 1
    if i == 0 and found:
        print(f'::notice ::{participant.repository} is number 1 in the ranking')
        return None
    if not found:
        print(f'::notice ::Welcome {participant.repository} and good luck for the competition')
    while i > 0:
        o = participants['participants'][i - 1]
        print(f'::notice ::Cloning \033[34mopponent\033[0m repository: {o["repository"]}')
        opponent = Participant(o['id'], o['repository'], o['private'], True)
        if opponent.data is not None:
            return opponent
        print(f'::notice ::{o["repository"]} is not participating any more, removing it')
        del participants['participants'][i - 1]
        _save_participants(participants)
        i -= 1
    print(f'::notice ::All opponents have left, {participant.repository} becomes number 1')
    return None


def _get_participant():
    input_participant = os.environ['INPUT_INDIVIDUAL_EVALUATION']
    split = input_participant.split(':')
    print(f'::notice ::Cloning \033[31mparticipant\033[0m repository: {split[1]}')
    participant = Participant(split[0], split[1], split[2] == 'true')
    return participant


def _copy_animator_files():
    animator_controller_source = os.path.join('metascript', 'animator')
    animator_controller_destination = os.path.join('controllers', 'animator')
    _copy_directory(animator_controller_source, animator_controller_destination)
    return animator_controller_destination


def _update_participant(p, participant, performance=None, date=True):
    p['id'] = participant.id
    p['repository'] = participant.repository
    p['private'] = participant.private
    p['name'] = participant.data['name']
    p['description'] = participant.data['description']
    p['country'] = participant.data['country']
    if participant.log is not None:
        p['log'] = participant.log
    if performance is not None:
        p['performance'] = performance
    if date:
        p['date'] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
            _update_participant(found_participant, opponent, rank + 1, False)
        else:  # insert participant at last but one position, move opponent to last position
            if found_opponent['performance'] != count - 1:
                print(f'::error ::Opponent should be ranked last in participants.json ({found_opponent["performance"]} != {count - 1})')
                sys.exit(1)
            _update_participant(found_opponent, opponent, count, False)
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
    new_destination_directory = os.path.join('storage', 'wb_animation_' + participant.id)
    _remove_directory(new_destination_directory)  # remove old animation
    _copy_directory(TMP_ANIMATION_DIRECTORY, new_destination_directory)
    _remove_directory(TMP_ANIMATION_DIRECTORY)
    _cleanup_storage_files(new_destination_directory)
    return


def _cleanup_storage_files(directory):
    if Path(directory).exists():
        for path in Path(directory).glob('*'):
            path = str(path)
            if path.endswith('.html') or path.endswith('.css'):
                os.remove(path)
            elif path.endswith('.json'):
                os.rename(path, directory + '/animation.json')
            elif path.endswith('.x3d'):
                os.rename(path, directory + '/scene.x3d')


def _remove_directory(directory):
    if Path(directory).exists():
        shutil.rmtree(directory)


def _copy_directory(source, destination):
    if Path(source).exists():
        shutil.copytree(source, destination)
