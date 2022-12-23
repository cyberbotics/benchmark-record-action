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

from datetime import datetime
import json
import os
import shutil
from pathlib import Path
from .animation import record_animations, TMP_ANIMATION_DIRECTORY
from .utils import git

ALLOW_PUSH = os.getenv('INPUT_ALLOW_PUSH', False)


class Participant:
    def __init__(self, id, repository):
        self.id = id
        self.repository = repository
        self.controller_path = os.path.join('controllers', id)
        print(f'\nCloning {repository} repository...')
        repo = 'https://{}:{}@github.com/{}'.format('Competition_Evaluator', os.environ['INPUT_REPO_TOKEN'], self.repository)
        git.clone(repo, self.controller_path)
        self.data = _load_json(os.path.join(self.controller_path, 'controllers', 'participant', 'participant.json'))
        print('Cloning complete.')


def competition(config):
    git.init()

    # Parse input participant
    participant = _get_participant()
    if config['world']['metric'] == 'ranking':  # run a bubble sort ranking
        while True:
            opponent = _get_opponent(participant)
            if opponent == None:  # we reached the top of the ranking
                break
            performance = int(_run_participant_controller(config, participant.controller_path, opponent.controller_path))
            _update_ranking(performance, participant, opponent)
            _update_animation_files(opponent if performance == 1 else participant)
            _remove_tmp_files(participant, opponent)
            if performance != 1:  # draw or loose, stopping duals
                break
    else:  # run a simple performance evaluation
        performance = _run_participant_controller(config, participant.controller_path)
        higher_is_better = config['world']['higher_is_better'].lower() == 'true'
        _update_performance(performance, participant, higher_is_better)
        _update_animation_files(participant)
        _remove_tmp_files(participant)

    if ALLOW_PUSH:
        git.push(message='record and update competition animations')


def _get_opponent(participant):
    participants = _load_participants()
    if participants is None:
        participants['participants'] = []
        p = {}
        _update_participant(p, participant, 1)
        participants['participants'].append(p)
        _save_participants(participants)
        print(f'Welcome {participant.repository}, you are the first participant there.')
        return None

    i = 0
    found = False
    for p in participants['participants']:
        if p['id'] == participant.id:
            found = True
            break
        i += 1
    if i == 0 and found:
        print(f'{participant.repository} is number 1 in the ranking.')
        return None
    if not found:
        print(f'Welcome {participant.repository} and good luck for the competition.')
    else:
        print(f'Welcome back {participant.repository} and good luck for this round.')
    opponent = participants['participant'][i - 1]
    return Participant(opponent['id'], opponent['repository'])


def _get_participant():
    input_participant = os.environ['INPUT_INDIVIDUAL_EVALUATION']
    split = input_participant.split(':')
    participant = Participant(split[0], split[1])
    return participant


def _run_participant_controller(config, controller_path, opponent_controller_path=None):
    print('\nRunning participant\'s controller...')
    animator_controller_source = os.path.join('metascript', 'animator')
    animator_controller_destination = os.path.join('controllers', 'animator')
    _copy_directory(animator_controller_source, animator_controller_destination)

    # Record animation and return performance
    performance = record_animations(config, controller_path, opponent_controller_path)

    _remove_directory(animator_controller_destination)
    print('done running controller and recording animations')
    return performance


def _update_participant(p, participant, performance):
    p['id'] = participant.id
    p['repository'] = participant.repository
    p['name'] = participant.data['name']
    p['description'] = participant.data['description']
    p['country'] = participant.data['country']
    p['performance'] = performance
    p['date'] = datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        print('Error: missing opponent in participants.json.')
        return
    count = len(participants['participants']) + 1
    if performance != 1:  # participant lost
        if found_participant:  # nothing to change
            return
        # we need to add the partipant at the bottom of the list
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
                print('Error: opponent should be ranked last in participants.json')
            _update_participant(found_opponent, participant, count - 1)
            p = {}
            _update_participant(p, opponent, count)
            participants['participants'].append(p)
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
        json.dump(object, f, ensure_ascii=False)


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


def _remove_tmp_files(participant, opponent=None):
    _remove_directory('tmp')
    _remove_directory('metascript')
    _remove_directory(participant.controller_path)
    if opponent:
        _remove_directory(opponent.controller_path)


def _remove_directory(directory):
    if Path(directory).exists():
        shutil.rmtree(directory)


def _copy_directory(source, destination):
    if Path(source).exists():
        shutil.copytree(source, destination)
