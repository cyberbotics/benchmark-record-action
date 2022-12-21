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


def competition(config):
    git.init()

    # Parse input participant
    participant = _get_participant()
    _clone_participant_controller(participant)
    if config['world']['metric'] == 'ranking':  # run a bubble sort ranking
        while True:
            opponent = _get_opponent(participant)
            if opponent == None:  # we reached the top of the ranking
                break
            _clone_participant_controller(opponent)
            performance = _run_participant_controller(config, participant.controller_path, opponent.controller_path)
            _update_ranking(performance, participant, opponent)
            _update_animation_files(opponent if performance == 1 else participant)
            _remove_tmp_files(participant, opponent)
            if performance == 0:  # draw or loose, stopping duals
                break
    else:  # run a simple performance evaluation
        performance = _run_participant_controller(config, participant.controller_path)
        _update_performance_line(performance, participant)
        _update_animation_files(participant)
        _remove_tmp_files(participant)

    if ALLOW_PUSH:
        git.push(message='record and update competition animations')


def _get_opponent(participant):
    with open('participants.txt') as f:
        upper_line = ''
        for line in f:
            line = line.strip()  # strip the line break
            split = line.split(':')
            if split[0] == participant.id:
                if upper_line == '':  # participant is number one, no opponent available
                    print(f'{participant.repository} is number 1 in the ranking.')
                    return None
                split = upper_line.split(':')
                return Participant(split[0], split[1])
            upper_line = line
    if upper_line == '':  # the first participant is stepping in
        with open('participants.txt', 'w') as f:
            f.write(f'{participant.id}:{participant.repository}:1:-:{datetime.today().strftime("%Y-%m-%d")}')
        print(f'Welcome {participant.repository}, you are the first participant there!')
        return None
    else:  # participant is a new comer, but there are other participants there, run against the last one
        print(f'Welcome {participant.repository} and good luck for the competition!')
        split = upper_line.split(':')
        return Participant(split[0], split[1])
    return None


def _get_participant():
    input_participant = os.environ['INPUT_INDIVIDUAL_EVALUATION']
    split = input_participant.split(':')
    participant = Participant(split[0], split[1])
    return participant


def _clone_participant_controller(participant):
    print('\nCloning participant repository...')
    repo = 'https://{}:{}@github.com/{}'.format(
        'Competition_Evaluator',
        os.environ['INPUT_REPO_TOKEN'],
        participant.repository
    )
    git.clone(repo, participant.controller_path)
    print('done fetching repo')


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


def _update_performance_line(performance, participant):  # only change the requested participant's performance
    updated_participant_line = f'{participant.id}:{participant.repository}:{performance}'
    tmp_participants = ''
    print('Updating participants.txt\n')
    with open('participants.txt', 'r') as f:
        found = False
        for line in f:
            line = line.strip()  # remove the line break
            if line.split(':')[0] == participant.id:
                new_line = updated_participant_line
                found = True
            else:
                new_line = line
            # concatenate the new string and add an end-line break
            tmp_participants += new_line + '\n'
        if not found:  # add at the end of the participants.txt file
            tmp_participants += updated_participant_line + '\n'

    with open('participants.txt', 'w') as f:
        f.write(tmp_participants.strip())


def _update_ranking(performance, participant, opponent):
    lines = []
    with open('participants.txt', 'r') as f:
        found_participant = -1
        found_opponent = -1
        counter = 0
        for line in f:
            line = line.strip()  # remove the line break
            split = line.split(':')
            id = split[0]
            ranking = int(split[2])
            if ranking != counter + 1:
                print('Error: Unordered ranking.')
                return
            if found_opponent >= 0:
                if id != participant.id:
                    print('Error: wrong ranking.')
                    return
                found_participant = counter
            elif id == opponent.id:
                found_opponent = counter
            lines.append(line)
            counter += 1
        if found_opponent == -1:
            print('Error: opponent not found in ranking.')
            return
        if found_participant == -1:
            if found_opponent != counter - 1:
                print('Error: opponent should be the last one in the ranking.')
                return
            if performance != 1:  # participant lost
                lines.append(f'{participant.id}:{participant.repository}:{counter + 1}')
            else:  # participant won: swap with opponent in the ranking
                lines[counter - 1] = f'{participant.id}:{participant.repository}:{counter}'
                lines.append(f'{opponent.id}:{opponent.repository}:{counter + 1}')
        elif performance == 1:  # swap participant and opponent in leaderboard
            lines[found_opponent] = f'{participant.id}:{participant.repository}:{found_opponent + 1}'
            lines[found_participant] = f'{opponent.id}:{opponent.repository}:{found_participant + 1}'
        else:  # nothing to change in the ranking
            return
    # write the updated ranking
    with open('participants.txt', 'w') as f:
        f.write('\n'.join(lines))


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
