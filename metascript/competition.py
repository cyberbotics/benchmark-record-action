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

import os
import shutil
from pathlib import Path
from .animation import record_animations, TMP_ANIMATION_DIRECTORY
from .utils import git

ALLOW_PUSH = os.getenv('INPUT_ALLOW_PUSH', False)


class Participant:
    def __init__(self, id, controller_repository):
        self.id = id
        (self.username, self.repository_name) = controller_repository.split('/')
        self.controller_repository = controller_repository
        self.controller_path = None


def competition(config):
    git.init()

    # Parse input participant
    participant = _get_participant()
    _clone_participant_controller(participant)
    performance = _run_participant_controller(config, participant.controller_path)
    _update_repo_files(performance, participant)
    _remove_tmp_files(participant)

    if ALLOW_PUSH:
        git.push(message='record and update competition animations')


def _get_participant():
    print('\nParsing participant...')

    input_participant = os.environ['INPUT_INDIVIDUAL_EVALUATION']
    participant = Participant(
        id=input_participant.split(':')[0],
        controller_repository=input_participant.split(':')[1].strip()
    )
    print('done parsing participant')
    return participant


def _clone_participant_controller(participant):
    print('\nCloning participant repository...')

    participant.controller_path = os.path.join('controllers', participant.id)

    repo = 'https://{}:{}@github.com/{}/{}'.format(
        'Competition_Evaluator',
        os.environ['INPUT_REPO_TOKEN'],
        participant.username,
        participant.repository_name
    )

    git.clone(repo, participant.controller_path)
    print('done fetching repo')


def _run_participant_controller(config, controller_path):
    print('\nRunning participant\'s controller...')
    animator_controller_source = os.path.join('metascript', 'animator')
    animator_controller_destination = os.path.join('controllers', 'animator')
    _copy_directory(animator_controller_source, animator_controller_destination)

    # Record animation and return performance
    performance = record_animations(config, TMP_ANIMATION_DIRECTORY, controller_path)

    _remove_directory(animator_controller_destination)
    print('done running controller and recording animations')
    return performance


def _update_repo_files(performance, participant):
    _update_performance_line(performance, participant)
    _update_animation_files(participant)


def _update_performance_line(performance, participant):

    # Only change the requested participant's performance
    updated_participant_line = f'{participant.id}:{participant.controller_repository}:{performance}'
    tmp_participants = ''
    print('Updating participants.txt\n')
    with open('participants.txt', 'r') as f:
        found = False
        for line in f:
            # stripping line break
            line = line.strip()
            test_id = line.split(':')[0]

            if test_id == participant.id:
                new_line = updated_participant_line.strip()
                found = True
            else:
                new_line = line
            # concatenate the new string and add an end-line break
            tmp_participants = tmp_participants + new_line + '\n'
        if not found:  # add at the end of the participants.txt file
            tmp_participants = tmp_participants + updated_participant_line.strip()

    with open('participants.txt', 'w') as f:
        f.write(tmp_participants)


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


def _remove_tmp_files(participant):
    _remove_directory('tmp')
    _remove_directory('metascript')
    _remove_directory(participant.controller_path)


def _remove_directory(directory):
    if Path(directory).exists():
        shutil.rmtree(directory)


def _copy_directory(source, destination):
    if Path(source).exists():
        shutil.copytree(source, destination)
