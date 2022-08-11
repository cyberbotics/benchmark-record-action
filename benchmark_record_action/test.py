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

import time
import re
import os
import shutil
from glob import glob
from pathlib import Path
import subprocess
from benchmark_record_action.config import RESOURCES_DIRECTORY
import benchmark_record_action.utils.git as git

UINT32_MAX = 4294967295
CHARACTER_SET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-"

class Competitor:
    def __init__(self, id, controller_repository):
        self.id = id
        self.username = controller_repository.split('/')[0]
        self.repository_name = controller_repository.split('/')[1]
        self.controller_path = None
        self.controller_name = None


def benchmark(config):
    world_config = config['world']

    init()
    competitors = get_competitors()
    clone_competitor_controllers(competitors)
    run_competitor_controllers(world_config, competitors)
    remove_competitor_controllers()
    push_modifications()


def init():
    print("\nInitializing safe directories...")
    subprocess.check_output(['git', 'config', '--global', '--add', 'safe.directory', '/github/workspace'])
    subprocess.check_output(['git', 'config', '--global', '--add', 'safe.directory', '/root/repo'])
    print("done")


def get_competitors():
    print("\nGetting competitor list...")
    if Path('competitors.txt').exists():
        competitors = []
        with Path('competitors.txt').open() as f:
            for competitor in f.readlines():
                competitors.append(
                    Competitor(
                        id = competitor.split(":")[0],
                        controller_repository = competitor.split(":")[1]
                    )
                )
    print("done")
    return competitors


def clone_competitor_controllers(competitors):
    print("\nCloning competitor controllers...")
    for competitor in competitors:
        competitor.controller_name = "competitor_" + competitor.id + "_" + competitor.username
        competitor.controller_path = os.path.join('controllers', competitor.controller_name)
        repo = 'https://{}:{}@github.com/{}/{}'.format(
            os.environ['BOT_USERNAME'],
            os.environ['BOT_PAT_KEY'],
            competitor.username,
            competitor.repository_name
        )
        subprocess.check_output(f'git clone {repo} {competitor.controller_path}', shell=True)
        python_filename = os.path.join(competitor.controller_path, 'controller.py')
        if os.path.exists(python_filename):
            os.rename(python_filename, os.path.join(competitor.controller_path, f'{competitor.controller_name}.py'))
    print("done")


def run_competitor_controllers(world_config, competitors):
    print("\nRunning competitor controllers...")
    for competitor in competitors:
        set_controller_name_to_world(world_config['file'], competitor.controller_name)
        record_benchmark_animation(world_config, competitor)
    print("done")


def set_controller_name_to_world(world_file, controller_name):
    print("  ", controller_name ,": Setting new controller in world...")
    world_content = None
    with open(world_file, 'r') as f:
        world_content = f.read()
    controller_expression = re.compile(rf'(DEF BENCHMARK_ROBOT.*?controller\ \")(.*?)(\")', re.MULTILINE | re.DOTALL)
    new_world_content = re.sub(controller_expression, rf'\1{controller_name}\3', world_content)
    with open(world_file, 'w') as f:
        f.write(new_world_content)


def generate_animation_recorder_vrml(duration, output):
    return (
        f'Robot {{\n'
        f'  name "animation_recorder_supervisor"\n'
        f'  controller "animation_recorder"\n'
        f'  controllerArgs [\n'
        f'    "--duration={duration}"\n'
        f'    "--output={output}"\n'
        f'  ]\n'
        f'  children [\n'
        f'    Receiver {{\n'
        f'      channel 1024\n'
        f'    }}\n'
        f'  ]\n'
        f'  supervisor TRUE\n'
        f'}}\n'
    )


def record_benchmark_animation(world_config, competitor):
    print("  ", competitor.controller_name, ": Recording animation...")

    # Create storage directory for animation
    world_name = world_config['file'].split('/')[1]
    destination_directory = '/tmp/animation'
    subprocess.check_output(['mkdir', '-p', destination_directory])

    # Append `animation_recorder` controller
    animation_recorder_vrml = generate_animation_recorder_vrml(
        duration = world_config['duration'],
        output = os.path.join(os.path.abspath('.'), destination_directory, world_name.replace('.wbt', '.html'))
    )
    with open(world_config['file'], 'r') as f:
        world_content = f.read()
    with open(world_config['file'], 'w') as f:
        f.write(world_content + animation_recorder_vrml)

    # Runs simulation in Webots
    out = subprocess.Popen(
        ['xvfb-run', 'webots', '--stdout', '--stderr', '--batch', '--mode=fast', '--no-rendering', 'worlds/robot_programming.wbt'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    run_flag = False
    while not out.poll():
        stdoutdata = out.stdout.readline()
        if stdoutdata:
            if not run_flag: run_flag = True
            #print(stdoutdata.decode('utf-8'))
        else:
            break
    # Removes `animation_recorder` controller
    with open(world_config['file'], 'w') as f:
        f.write(world_content)

    # Copy files to new directory
    if run_flag:
        new_destination_directory = os.path.join('storage', 'Wb_' + id_to_storage_string(int(competitor.id)))
        print("  ", competitor.controller_name, ": Copying files to", new_destination_directory)
        subprocess.check_output(['mkdir', '-p', new_destination_directory])
        subprocess.check_output(f'mv {destination_directory}/* {new_destination_directory}', shell=True)
        cleanup_storage_files(competitor.controller_name, new_destination_directory)
    else:
        print("  ", competitor.controller_name, ": Error: could not run controller")

    print("  ", competitor.controller_name, ": done")

def cleanup_storage_files(name, directory):
    print("  ", name, ": Clean-up files in", directory)
    for path in Path(directory).glob('*'):
        path = str(path)
        if path.endswith('.html') or path.endswith('.css'):
            os.remove(path)
        elif path.endswith('.json'):
            os.rename(path, directory + '/animation.json')
        elif path.endswith('.x3d'):
            os.rename(path, directory + '/scene.x3d')

def remove_competitor_controllers():
    print("\nRemoving competitor controller directories...")
    for path in Path('controllers').glob('*'):
        controller = str(path).split('/')[1]
        if controller.startswith('competitor'):
            shutil.rmtree(path)
    print("done")

def push_modifications():
    print("\nCommitting and pushing updates...")
    git.push(message="record and update benchmark animations")
    print("done")

def test_push():
    print("Listing directories and files in repository: ", os.environ['GITHUB_REPOSITORY'], " (on branch: ", os.environ['GITHUB_REF'].split('/')[-1], ")")
    for path in Path('').glob('*'):
        path = str(path)
        print('path: ', path)

    print("\nMoving directory...")

    for path in Path('').glob('*'):
        path = str(path)
        if path == 'AxjD2FU':
            shutil.move(path, 'storage')

    print("\nListing files after move:")
    for path in Path('').glob('*'):
        path = str(path)
        print('path: ', path)

    print("Commit ad push changes to branch: ", os.environ['GITHUB_REF'].split('/')[-1])
    git.push(message="change file location")


def id_to_storage_string(id):
    s = int(str(UINT32_MAX - id).zfill(10)[::-1])
    storage_string = ""
    for i in range(6):
        b = (s >> (6 * i)) & 63
        storage_string += CHARACTER_SET[b]
    return storage_string


def storage_string_to_id(storage_string):
    n = 0
    for i in range(6):
        n += CHARACTER_SET.find(storage_string[i]) << (6 * i)
    id = UINT32_MAX - int(str(n).zfill(10)[::-1])
    return id
