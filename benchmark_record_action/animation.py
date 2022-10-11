#!/usr/bin/env python3
#
# Copyright 1996-2020 Cyberbotics Ltd.
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


def generate_animation_recorder_vrml(duration, output, controllers, metric):
    return (
        f'DEF ANIMATION_RECORDER_SUPERVISOR Robot {{\n'
        f'  name "animation_recorder_supervisor"\n'
        f'  controller "animation_recorder"\n'
        f'  controllerArgs [\n'
        f'    "--duration={duration}"\n'
        f'    "--output={output}"\n'
        f'    "--controllers={controllers}"\n'
        f'    "--metric={metric}"\n'
        f'  ]\n'
        f'  children [\n'
        f'    Receiver {{\n'
        f'      channel 1024\n'
        f'    }}\n'
        f'  ]\n'
        f'  supervisor TRUE\n'
        f'}}\n'
    )

def record_animations(world_config, destination_directory, controllers):
    # Create temporary directory
    subprocess.check_output(['mkdir', '-p', destination_directory])

    # Append `animation_recorder` controller
    animation_recorder_vrml = generate_animation_recorder_vrml(
        duration = world_config['max-duration'],
        output = os.path.join(os.path.abspath('.'), destination_directory),
        controllers = controllers,
        metric = world_config['metric']
    )
    with open(world_config['file'], 'r') as f:
        world_content = f.read()
    with open(world_config['file'], 'w') as f:
        f.write(world_content + animation_recorder_vrml)

    # Runs simulation in Webots
    # real-time stdout of webots (still buggy)
    
    webots_process = subprocess.Popen(
        ['xvfb-run', 'webots', '--stdout', '--stderr', '--batch', '--mode=fast', '--no-rendering', world_config['file']],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )

    while webots_process.poll() is None:
        realtime_output = webots_process.stdout.readline()
        print(realtime_output.replace('\n', ''))
    
    print(f'out.stdout -> {webots_process.stdout}')
    print(f'out.stdout readline-> {webots_process.stdout.readline()}')
    
    
    # no stdout output
    """
    webots_process = subprocess.run(
        ['xvfb-run', 'webots', '--stdout', '--stderr', '--batch', '--mode=fast', '--no-rendering', world_config['file']],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )
    """
    # Removes `animation_recorder` controller
    with open(world_config['file'], 'w') as f:
        f.write(world_content)
