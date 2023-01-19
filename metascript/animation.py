#!/usr/bin/env python3
#
# Copyright 1996-2023 Cyberbotics Ltd.
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
import select
import subprocess
import sys

TMP_ANIMATION_DIRECTORY = 'tmp'
PERFORMANCE_KEYWORD = 'performance:'


def record_animations(gpu, config, participant_controller_path, participant_name,
                      opponent_controller_path=None, opponent_name=''):
    world_config = config['world']
    performance = 0

    # Create temporary directory for animations, textures and meshes
    # This is necessary otherwise we cannot delete these files from outside of the container
    subprocess.check_output(['mkdir', '-p', os.path.join(TMP_ANIMATION_DIRECTORY, 'textures')])
    subprocess.check_output(['mkdir', '-p', os.path.join(TMP_ANIMATION_DIRECTORY, 'meshes')])

    # Temporary world file changes
    with open(world_config['file'], 'r') as f:
        original_world_content = f.read()
    world_content = original_world_content.replace('controller "participant"', 'controller "<extern>"')
    if opponent_controller_path:
        world_content = world_content.replace('controller "opponent"', 'controller "<extern>"')
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
    print('::group::Building \033[32mWebots\033[0m docker')
    recorder_build = subprocess.Popen(
        [
            'docker', 'build',
            '--tag', 'recorder-webots',
            '--file', 'Dockerfile',
            '.'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )
    return_code = _get_realtime_stdout(recorder_build)
    print('::endgroup::')
    if return_code != 0:
        print('::error ::Missing or misconfigured Dockerfile while building the Webots container')
        sys.exit(1)

    print('::group::Building \033[31mparticipant\033[0m docker')
    participant_controller_build = subprocess.Popen(
        [
            'docker', 'build',
            '--tag', 'participant-controller',
            '--file', f'{participant_controller_path}/controllers/Dockerfile',
            '--build-arg', 'WEBOTS_CONTROLLER_URL=tcp://172.17.0.1:3005/participant',
            f'{participant_controller_path}/controllers'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )
    return_code = _get_realtime_stdout(participant_controller_build)
    print('::endgroup::')
    if return_code != 0:
        print('::error ::Missing or misconfigured Dockerfile while building the participant controller container')
        sys.exit(1)

    if opponent_controller_path:
        print('::group::Building \033[34mopponent\033[0m docker')
        opponent_controller_build = subprocess.Popen(
            [
                'docker', 'build',
                '--tag', 'opponent-controller',
                '--file', f'{opponent_controller_path}/controllers/Dockerfile',
                '--build-arg', 'WEBOTS_CONTROLLER_URL=tcp://172.17.0.1:3005/opponent',
                f'{opponent_controller_path}/controllers'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8'
        )
        return_code = _get_realtime_stdout(opponent_controller_build)
        print('::endgroup::')
        if return_code != 0:
            print('::warning ::Missing or misconfigured Dockerfile while building the opponent controller container')
            performance = 1

    # clearning containers possibly remaining after the last job
    participant_controller_container_id = _get_container_id('participant-controller')
    if participant_controller_container_id != '':
        subprocess.run(['docker', 'kill', participant_controller_container_id], stdout=subprocess.DEVNULL)
    opponent_controller_container_id = _get_container_id('opponent-controller')
    if opponent_controller_container_id != '':
        subprocess.run(['docker', 'kill', opponent_controller_container_id], stdout=subprocess.DEVNULL)

    # Run Webots container with Popen to read the stdout
    print('::group::Running Webots')
    command_line = ['docker', 'run', '--tty', '--rm']
    if gpu:
        command_line += ['--gpus=all', '--env', 'DISPLAY',
                         '--volume', '/tmp/.X11-unix:/tmp/.X11-unix:rw']
    else:
        command_line += ['--init']

    command_line += [
        '--mount', 'type=bind,' +
                   f'source={os.getcwd()}/{TMP_ANIMATION_DIRECTORY},' +
                   f'target=/usr/local/webots-project/{TMP_ANIMATION_DIRECTORY}',
        '--publish', '3005:1234',
        '--env', 'CI=true',
        '--env', f'PARTICIPANT_NAME={participant_name}',
        '--env', f'OPPONENT_NAME={opponent_name}',
        'recorder-webots']

    if not gpu:
        command_line += ['xvfb-run', '-e', '/dev/stdout', '-a']
    command_line += ['webots', '--stdout', '--stderr', '--batch', '--minimize', '--mode=fast',
                     '--no-rendering', f'/usr/local/webots-project/{world_config["file"]}']

    webots_docker = subprocess.Popen(command_line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')

    participant_docker = None
    opponent_docker = None
    participant_controller_connected = False
    opponent_controller_connected = False
    timeout = False

    while webots_docker.poll() is None:
        fds = [webots_docker.stdout]
        if participant_docker:
            fds.append(participant_docker.stdout)
        if opponent_docker:
            fds.append(opponent_docker.stdout)
        fd = select.select(fds, [], [])[0]
        webots_line = webots_docker.stdout.readline().strip() if webots_docker.stdout in fd else None
        participant_available = participant_docker and participant_docker.stdout in fd
        participant_line = participant_docker.stdout.readline().strip() if participant_available else None
        opponent_available = opponent_docker and opponent_docker.stdout in fd
        opponent_line = opponent_docker.stdout.readline().strip() if opponent_available else None
        if participant_line:
            print(f'\033[31m{participant_line}\033[0m')
        if opponent_line:
            print(f'\033[34m{opponent_line}\033[0m')
        if webots_line is None:
            continue
        print(f'\033[32m{webots_line}\033[0m')
        if "' extern controller: waiting for connection on ipc://" in webots_line:
            if participant_docker is None and "INFO: 'participant' " in webots_line:
                participant_docker = subprocess.Popen(['docker', 'run', '--rm', 'participant-controller'],
                                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
            elif opponent_docker is None and "INFO: 'opponent' " in webots_line:
                opponent_docker = subprocess.Popen(['docker', 'run', '--rm', 'opponent-controller'],
                                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
        elif "' extern controller: connected" in webots_line:
            if "INFO: 'participant' " in webots_line:
                participant_controller_connected = True
            elif "INFO: 'opponent' " in webots_line:
                opponent_controller_connected = True
        elif PERFORMANCE_KEYWORD in webots_line:
            performance = float(webots_line.strip().replace(PERFORMANCE_KEYWORD, ''))
            break
        elif 'Controller timeout' in webots_line:
            timeout = True
            break
    if webots_docker.returncode:
        print(f'::error ::Webots container exited with code {webots_docker.returncode}')
        sys.exit(1)
    if not participant_docker:
        print('::error ::Competition finished before launching the participant controller: ' +
              'check that the controller in the world file is named "participant"')
        sys.exit(1)
    if not participant_controller_connected:
        print('::error ::Competition finished before the participant controller connected to Webots: ' +
              'your controller crashed. Please debug your controller locally before submitting it')
        sys.exit(1)
    if opponent_docker and not opponent_controller_connected:
        print('::warning ::Competition finished before the opponent controller connected to Webots: ' +
              'the opponent controller failed conntected to Webots, therefore you won')
        performance = 1

    print('::endgroup::')
    print('::group::Closing the containers')
    webots_container_id = _get_container_id('recorder-webots')
    if webots_container_id != '':  # Closing Webots with SIGINT to trigger animation export
        subprocess.run(['docker', 'exec', webots_container_id, 'pkill', '-SIGINT', 'webots-bin'])
    print('::endgroup::')

    # restore temporary file changes
    with open(world_config['file'], 'w') as f:
        f.write(original_world_content)

    # compute performance line
    if timeout:
        if world_config['metric'] == 'time' and world_config['higher-is-better']:
            # time-duration competition completed with maximum time
            performance = float(world_config['max-duration'])
        else:  # competition failed: time limit reached
            print(f'::error ::Your controller took more than {world_config["max-duration"]} seconds to complete the competition')
            sys.exit(1)
    return performance


def _get_container_id(container_name):
    container_id = subprocess.check_output(['docker', 'ps', '-f', f'ancestor={container_name}', '-q']).decode('utf-8').strip()
    return container_id


def _get_realtime_stdout(process):
    while process.poll() is None:
        realtime_output = process.stdout.readline()
        if realtime_output:
            print(realtime_output.strip())
    return process.returncode
