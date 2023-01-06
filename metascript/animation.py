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

import subprocess
import os
from datetime import datetime
from math import floor

TMP_ANIMATION_DIRECTORY = 'tmp/animation'
PERFORMANCE_KEYWORD = 'performance:'


def record_animations(config, controller_path, opponent_controller_path):
    world_config = config['world']
    default_controller_name = config['dockerCompose'].split('/')[2]

    # Create temporary directory
    subprocess.check_output(['mkdir', '-p', TMP_ANIMATION_DIRECTORY])

    # Temporary file changes*:
    with open(world_config['file'], 'r') as f:
        world_content = f.read()
    world_content = world_content.replace(f'controller "{default_controller_name}"', 'controller "<extern>"')
    if opponent_controller_path:
        world_content = world_content.replace(f'controller "opponent"', 'controller "<extern>"')
    world_content += f'''
    DEF ANIMATION_RECORDER_SUPERVISOR Robot {{
    name "animation_recorder_supervisor"
    controller "animator"
    controllerArgs [
        "--duration={world_config['max-duration']}"
        "--output={TMP_ANIMATION_DIRECTORY}"
    ]
    supervisor TRUE
    }}
    '''

    with open(world_config['file'], 'w') as f:
        f.write(world_content)

    # Building the Docker containers
    recorder_build = subprocess.Popen(
        [
            'docker', 'build',
            '-t', 'recorder-webots',
            '-f', 'Dockerfile',
            '--build-arg', f'WORLD_PATH={world_config["file"]}',
            '.'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )
    _get_realtime_stdout(
        recorder_build,
        'Error while building the recorder container',
        'Missing or misconfigured Dockerfile'
    )

    controller_build = subprocess.Popen(
        [
            'docker', 'build',
            '-t', 'controller-docker',
            '-f', f'{controller_path}/controllers/{default_controller_name}/Dockerfile.extern',
            '--build-arg', f'DEFAULT_CONTROLLER={default_controller_name}',
            '--build-arg', 'WEBOTS_CONTROLLER_URL=tcp://172.17.0.1:3005/participant',
            f'{controller_path}/controllers/{default_controller_name}'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )
    _get_realtime_stdout(
        controller_build,
        'Error while building the participant controller container',
        'Missing or misconfigured Dockerfile'
    )

    if opponent_controller_path:
        opponent_controller_build = subprocess.Popen(
            [
                'docker', 'build',
                '-t', 'opponent-controller-docker',
                '-f', f'{opponent_controller_path}/controllers/{default_controller_name}/Dockerfile.extern',
                '--build-arg', f'DEFAULT_CONTROLLER={default_controller_name}',
                '--build-arg', 'WEBOTS_CONTROLLER_URL=tcp://172.17.0.1:3005/opponent',
                f'{opponent_controller_path}/controllers/{default_controller_name}'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8'
        )
        _get_realtime_stdout(
            opponent_controller_build,
            'Error while building the opponent controller container',
            'Missing or misconfigured Dockerfile'
        )

    # Run Webots container with Popen to read the stdout
    webots_docker = subprocess.Popen(
        [
            'docker', 'run', '-t', '--rm', '--init',
            '--mount', f'type=bind,source={os.getcwd()}/{TMP_ANIMATION_DIRECTORY},target=/usr/local/webots-project/{TMP_ANIMATION_DIRECTORY}',
            '-p', '3005:1234',
            '--env', 'CI=true',
            'recorder-webots'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )

    launched_controller = False
    participant_docker = None
    opponent_docker = None
    participant_controller_connected = False
    opponent_controller_connected = False
    performance = 0
    timeout = False

    while webots_docker.poll() is None:
        realtime_output = _print_stdout(webots_docker)
        if not launched_controller and 'waiting for connection' in realtime_output:
            participant_docker = subprocess.Popen(['docker', 'run', '--rm', 'controller-docker'],
                                                  stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            if opponent_controller_path:
                opponent_docker = subprocess.Popen(['docker', 'run', '--rm', 'opponent-controller-docker'],
                                                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            launched_controller = True
        if launched_controller:
            if participant_docker is not None:
                _print_stdout(participant_docker)
                if opponent_docker is not None:
                    _print_stdout(opponent_docker)
            if ' extern controller: connected' in realtime_output:
                if "'participant' " in realtime_output:
                    participant_controller_connected = True
                elif "'opponent' " in realtime_output:
                    opponent_controller_connected = True
        if PERFORMANCE_KEYWORD in realtime_output:
            performance = float(realtime_output.strip().replace(PERFORMANCE_KEYWORD, ''))
            break
        elif 'Controller timeout' in realtime_output:
            timeout = True
            break
    if webots_docker.returncode:
        _print_error(f'Webots container exited with code {webots_docker.returncode}',
                     'Error while running the Webots container.')
    if not launched_controller:
        _print_error('Competition finished before launching the participant controller',
                     'Check that the controller in the world file is the same as the one in webots.yml.')
    if not participant_controller_connected:
        _print_error('Competition finished before the participant controller connected to Webots',
                     'Your controller crashed. Please debug your controller locally before submitting it.')
        performance = 0
    if not opponent_controller_connected:
        _print_error('Competition finished before the opponent controller connected to Webots',
                     'Therefore, you won.')
        performance = 1

    print('Closing the containers...')
    webots_container_id = _get_container_id('recorder-webots')
    if webots_container_id != '':  # Closing Webots with SIGINT to trigger animation export
        subprocess.run(['/bin/bash', '-c', f'docker exec {webots_container_id} pkill -SIGINT webots-bin'])
    controller_container_id = _get_container_id('controller-docker')
    if controller_container_id != '':
        subprocess.run(['/bin/bash', '-c', f'docker kill {controller_container_id}'])
    if opponent_controller_path:
        opponent_controller_container_id = _get_container_id('opponent-controller-docker')
        if opponent_controller_container_id != '':
            subprocess.run(['/bin/bash', '-c', f'docker kill {opponent_controller_container_id}'])

    # restore temporary file changes
    with open(world_config['file'], 'w') as f:
        f.write(world_content)

    # compute performance line
    metric = world_config['metric']
    higher_is_better = world_config['higher-is-better'] == 'true'
    if timeout:
        if metric == 'time' and higher_is_better:  # time-duration competition completed with maximum time
            performance = float(world_config['max-duration'])
        else:  # competition failed: time limit reached
            raise Exception(
                f'::error ::Your controller took more than {world_config["max-duration"]} seconds to complete the competition.'
            )

    return performance

def _time_convert(time):
    minutes = time / 60
    absolute_minutes = floor(minutes)
    minutes_string = str(absolute_minutes).zfill(2)
    seconds = (minutes - absolute_minutes) * 60
    absolute_seconds = floor(seconds)
    seconds_string = str(absolute_seconds).zfill(2)
    cs = floor((seconds - absolute_seconds) * 100)
    cs_string = str(cs).zfill(2)
    return minutes_string + '.' + seconds_string + '.' + cs_string

def _get_container_id(container_name):
    container_id = subprocess.check_output(['docker', 'ps', '-f', f'ancestor={container_name}', '-q']).decode('utf-8').strip()
    return container_id

def _get_realtime_stdout(process, error_title, error_message):
    while process.poll() is None:
        _print_stdout(process)
    if process.returncode != 0:
        _print_error(error_title, error_message)

def _print_stdout(process):
    realtime_output = process.stdout.readline()
    if realtime_output:
        print(realtime_output.strip())
    return realtime_output

def _print_error(title, message):
    print(f'::error title={title}::{message}')
    raise Exception(f'{title}\n{message}')
