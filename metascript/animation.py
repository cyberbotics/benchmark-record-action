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


# return 1 if participant wins, 0 if participant loses and -1 if participant fails (due to an error)
def record_animations(gpu, config, participant_controller_path, participant_name,
                      opponent_controller_path=None, opponent_name='', first_run=True):
    world_config = config['world']
    performance = 0

    # Create temporary directory for animations, textures and meshes
    # This is necessary otherwise we cannot delete these files from outside of the container
    subprocess.check_output(['mkdir', '-p', os.path.join(TMP_ANIMATION_DIRECTORY, 'textures')])
    subprocess.check_output(['mkdir', '-p', os.path.join(TMP_ANIMATION_DIRECTORY, 'meshes')])

    if first_run:
        # Temporary world file changes
        with open(world_config['file'], 'r') as f:
            world_content = f.read()
        world_content = world_content.replace('controller "participant"', 'controller "<extern>"')
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

        print(f'::group::Building \033[31mparticipant\033[0m docker (\033[31m{participant_name}\033[0m)')
        participant_controller_build = subprocess.Popen(
            [
                'docker', 'build',
                '--tag', 'participant-controller',
                '--file', f'{participant_controller_path}/controllers/Dockerfile',
                '--build-arg', 'WEBOTS_CONTROLLER_URL=participant',
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
            return -1

    if opponent_controller_path:
        print(f'::group::Building \033[34mopponent\033[0m docker (\033[34m{opponent_name}\033[0m)')
        opponent_controller_build = subprocess.Popen(
            [
                'docker', 'build',
                '--tag', 'opponent-controller',
                '--file', f'{opponent_controller_path}/controllers/Dockerfile',
                '--build-arg', 'WEBOTS_CONTROLLER_URL=opponent',
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

    webots_old_container_id = _get_container_id('recorder-webots')
    if webots_old_container_id != '':  # A zombie webots container may still be there due to a previous crash
        print('::warning ::Killing a Webots zombie process left by the previous job')
        subprocess.run(['docker', 'kill', webots_old_container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Run Webots container with Popen to read the stdout
    if opponent_controller_path:
        print(f'::group::Running game in \033[32mWebots\033[0m: \033[31m{participant_name}\033[0m '
              + f'versus \033[34m{opponent_name}\033[0m')
    else:
        print(f'::group::Running evaluation in \033[32mWebots\033[0m of \033[31m{participant_name}\033[0m')
    command_line = ['docker', 'run', '--tty', '--rm']
    cpu_count = os.cpu_count()
    if cpu_count == 1:
        webots_cpuset_cpus = '0'
        participant_cpuset_cpus = '0'
        opponent_cpuset_cpus = '0'
    elif cpu_count == 2:
        webots_cpuset_cpus = '0'
        participant_cpuset_cpus = '1'
        opponent_cpuset_cpus = '1'
    elif cpu_count == 4:
        webots_cpuset_cpus = '0,1'
        participant_cpuset_cpus = '2'
        opponent_cpuset_cpus = '3'
    elif cpu_count >= 8:
        cpus = world_config['cpus'] if 'cpus' in world_config else 1
        if cpus == 3:
            webots_cpuset_cpus = '0,4'
            participant_cpuset_cpus = '1,5,3'
            opponent_cpuset_cpus = '2,6,7'
        elif cpus == 2:
            webots_cpuset_cpus = '0,3,4,7'
            participant_cpuset_cpus = '1,5'
            opponent_cpuset_cpus = '2,6'
        else:
            webots_cpuset_cpus = '0,3,4,5,6,7'
            participant_cpuset_cpus = '1'
            opponent_cpuset_cpus = '2'
            if cpus != 1:
                print(f'::warning ::Unsupported number of CPUs for controllers: {cpus} (cpus in webots.yml)')
        if cpu_count != 8:
            print(f'::warning ::CPU core count is {cpu_count}, using only 8 cores')
    else:
        webots_cpuset_cpus = None
        participant_cpuset_cpus = None
        opponent_cpuset_cpus = None
        print(f'::warning ::Unsupported CPU count value: {cpu_count}')

    if webots_cpuset_cpus:
        command_line += [f'--cpuset-cpus={webots_cpuset_cpus}']

    if gpu:
        command_line += ['--gpus', 'all', '--env', 'DISPLAY',
                         '--volume', '/tmp/.X11-unix:/tmp/.X11-unix:ro']
    else:
        command_line += ['--init']

    if opponent_controller_path:
        command_line += ['--volume', '/tmp/webots-1234/ipc/opponent:/tmp/webots-1234/ipc/opponent']

    command_line += [
        '--volume', '/tmp/webots-1234/ipc/participant:/tmp/webots-1234/ipc/participant',
        '--mount', 'type=bind,'
                   + f'source={os.getcwd()}/{TMP_ANIMATION_DIRECTORY},'
                   + f'target=/usr/local/webots-project/{TMP_ANIMATION_DIRECTORY}',
        '--env', 'CI=true',
        '--env', f'PARTICIPANT_NAME={participant_name}',
        '--env', f'OPPONENT_NAME={opponent_name}',
        'recorder-webots']

    if not gpu:
        command_line += ['xvfb-run', '-e', '/dev/stdout', '-a']
    command_line += ['webots', '--stdout', '--stderr', '--batch', '--minimize', '--mode=fast',
                     '--no-rendering', f'/usr/local/webots-project/{world_config["file"]}']

    webots_docker = subprocess.Popen(command_line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
    print(' '.join(command_line))

    participant_docker = None
    opponent_docker = None
    participant_controller_connected = False
    opponent_controller_connected = False
    timeout = False
    participant_line_count = 0
    opponent_line_count = 0
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
            if participant_line_count < 100:
                print(f'\033[31m{participant_line}\033[0m')
            elif participant_line_count == 100:
                print(f'Participant \033[31m{participant_name}\033[0m printed more than 100 lines, ignoring further prints')
            participant_line_count += 1
        if opponent_line:
            if opponent_line_count < 100:
                print(f'\033[34m{opponent_line}\033[0m')
            elif opponent_line_count == 100:
                print(f'Opponent \033[34m{opponent_name}\033[0m printed more than 100 lines, ignoring further prints')
            opponent_line_count += 1
        if webots_line is None:
            continue
        print(f'\033[32m{webots_line}\033[0m')
        if "' extern controller: connected" in webots_line:
            if webots_line.startswith("INFO: 'participant' "):
                participant_controller_connected = True
            elif webots_line.startswith("INFO: 'opponent' "):
                opponent_controller_connected = True
        elif "' extern controller: " in webots_line:
            command_line = ['docker', 'run', '--rm']
            if gpu:
                command_line += ['--gpus', 'all']
            if 'memory' in world_config:
                command_line += [f'--memory={world_config["memory"]}']
            command_line += ['--network', 'none', '--volume']
            if participant_docker is None and webots_line.startswith("INFO: 'participant' "):
                command_line += ['/tmp/webots-1234/ipc/participant:/tmp/webots-1234/ipc/participant']
                if participant_cpuset_cpus:
                     command_line += [f'--cpuset-cpus={participant_cpuset_cpus}']
                command_line += ['participant-controller']
                participant_docker = subprocess.Popen(command_line,
                                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
                print(' '.join(command_line))
            elif opponent_docker is None and webots_line.startswith("INFO: 'opponent' "):
                command_line += ['/tmp/webots-1234/ipc/opponent:/tmp/webots-1234/ipc/opponent']
                if opponent_cpuset_cpus:
                    command_line += [f'--cpuset-cpus={opponent_cpuset_cpus}']
                command_line += ['opponent-controller']
                opponent_docker = subprocess.Popen(command_line,
                                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
                print(' '.join(command_line))
        elif PERFORMANCE_KEYWORD in webots_line:
            performance = float(webots_line.strip().replace(PERFORMANCE_KEYWORD, ''))
            break
        elif 'Controller timeout' in webots_line:
            timeout = True
            break
    if webots_docker.returncode:
        print(f'::error ::Webots container exited with code {webots_docker.returncode}')
        performance = -1
    if not participant_docker:
        print('::error ::Competition finished before launching the participant controller: '
              + 'check that the controller in the world file is named "participant"')
        performance = -1
    if not participant_controller_connected:
        print('::error ::Competition finished before the participant controller connected to Webots: '
              + 'your controller crashed. Please debug your controller locally before submitting it')
        performance = -1
    if opponent_docker and not opponent_controller_connected:
        print('::warning ::Competition finished before the opponent controller connected to Webots: '
              + 'the opponent controller failed to connect to Webots, therefore you won')
        performance = 1

    _close_containers()

    # compute performance line
    if timeout:
        if world_config['metric'] == 'time' and world_config['higher-is-better']:
            # time-duration competition completed with maximum time
            performance = float(world_config['max-duration'])
        else:  # competition failed: time limit reached
            print(f'::error ::Your controller took more than {world_config["max-duration"]} seconds'
                  ' to complete the competition')
            sys.exit(1)
    print('::endgroup::')
    if opponent_controller_path:
        print(f'::notice ::{participant_name} {"won" if performance == 1 else "lost"} over {opponent_name}')
    else:
        print(f'::notice ::The performance of {participant_name} is: {performance}')
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


def _close_containers():  # clearing containers possibly remaining after the last job
    webots_container_id = _get_container_id('recorder-webots')
    if webots_container_id != '':  # Closing Webots with SIGINT to trigger animation export
        subprocess.run(['docker', 'exec', webots_container_id, 'pkill', '-SIGINT', 'webots-bin'])
    participant_controller_container_id = _get_container_id('participant-controller')
    if participant_controller_container_id != '':
        subprocess.run(
            ['docker', 'kill', participant_controller_container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    opponent_controller_container_id = _get_container_id('opponent-controller')
    if opponent_controller_container_id != '':
        subprocess.run(
            ['docker', 'kill', opponent_controller_container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
