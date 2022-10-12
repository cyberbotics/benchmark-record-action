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

import os
import shutil
from pathlib import Path
import subprocess
from benchmark_record_action.animation import record_animations
import benchmark_record_action.utils.git as git


class Competitor:
    def __init__(self, id, controller_repository):
        self.id = id
        self.username = controller_repository.split('/')[0]
        self.repository_name = controller_repository.split('/')[1]
        self.controller_repository = controller_repository
        self.controller_path = None
        self.controller_name = None


def benchmark(config):
    # get world configuration
    world_config = config['world']

    # Initialite Git
    git.init()

    # Get competitors
    competitors = _get_competitors()

    # Clone and run controllers
    _clone_competitor_controllers(competitors)
    _run_competitor_controllers(world_config, competitors)
    _remove_competitor_controllers()

    # Commit and Push updates
    git.push(message="record and update benchmark animations")


def _get_competitors():
    print("\nGetting competitor list...")

    # if it is an individual evaluation
    if len(os.environ['INPUT_INDIVIDUAL_EVALUATION']) != 0 :
        competitors = []
        competitor = os.environ['INPUT_INDIVIDUAL_EVALUATION']
        competitors.append(
            Competitor(
                id = competitor.split(":")[0],
                controller_repository = competitor.split(":")[1].replace("\n", "")
            )
        )
        return competitors
    
    # if it is a general evaluation
    elif Path('competitors.txt').exists():
        competitors = []
        with Path('competitors.txt').open() as f:
            for competitor in f.readlines():
                competitors.append(
                    Competitor(
                        id = competitor.split(":")[0],
                        controller_repository = competitor.split(":")[1].replace("\n", "")
                    )
                )

    print("done getting competitor list")

    return competitors


def _clone_competitor_controllers(competitors):
    print("\nCloning competitor controllers...")

    for competitor in competitors:
        competitor.controller_name = "competitor_" + competitor.id + "_" + competitor.username
        competitor.controller_path = os.path.join('controllers', competitor.controller_name)

        # Copy controller folder to correctly named controller folder (using subversion)
        out = subprocess.check_output(
                [
                    'svn', 'export', 'https://github.com/{}/{}/trunk/controllers/{}'.format(
                        competitor.username, competitor.repository_name,
                        os.environ['INPUT_DEFAULT_CONTROLLER_NAME']
                    ),
                    competitor.controller_path,
                    '--username', 'Benchmark_Evaluator', '--password', os.environ['INPUT_FETCH_TOKEN'],
                    '--quiet', '--non-interactive'
                ]
            )
        
        # Rename controller files to the correct name
        for filename in os.listdir(competitor.controller_path):
            name, ext = os.path.splitext(filename)

            if name == os.environ['INPUT_DEFAULT_CONTROLLER_NAME']:
                os.rename(
                    f'{competitor.controller_path}/{filename}',
                    f'{competitor.controller_path}/{competitor.controller_name}{ext}'
                    )


    print("done fetching controllers")


def _run_competitor_controllers(world_config, competitors):
    print("\nRunning competitor controllers...")

    # Save original world file
    with open(world_config['file'], 'r') as f:
        world_content = f.read()

    # Run controllers and record animations
    _record_benchmark_animations(world_config, competitors)

    # Revert to original world file
    with open(world_config['file'], 'w') as f:
        f.write(world_content)

    print("done running competitors' controllers")


def _record_benchmark_animations(world_config, competitors):
    # Variables and dictionary
    controllers = []
    id_column = []
    repository_column = []
    for competitor in competitors:
        controllers.append(competitor.controller_name)
        id_column.append(competitor.id)
        repository_column.append(competitor.controller_repository)
    competitor_dict = dict(zip(id_column, repository_column))
    destination_directory = 'tmp/animation'

    # Record animations and save performances
    record_animations(world_config, destination_directory, controllers)

    # Get results
    with Path(destination_directory + '/competitors.txt').open() as f:
        performances = f.readlines()
    
    if len(os.environ['INPUT_INDIVIDUAL_EVALUATION']) != 0 :
        _replace_one_performance(performances)
    else:
        _replace_all_performances(performances)

    # Remove tmp file
    shutil.rmtree('tmp')

    print('done recording animations')

def _replace_all_performances(performances):

    # Delete old files
    for path in Path('storage').glob('*'):
        path = str(path)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    # Move animations and performances
    updated_competitors = ""
    for performance in performances:
        competitor_id = performance.split(':')[0]
        competitor_repository = competitor_dict.get(competitor_id)
        performance_value = performance.split(':')[1]
        performance_string = performance.split(':')[2]
        date = performance.split(':')[3]
        updated_competitors += competitor_id + ':' + competitor_repository + ':' + performance_value + ':' + \
            performance_string + ':' + date

        controller_name = "competitor_" + competitor_id + "_" + competitor_repository.split('/')[0]
        new_destination_directory = os.path.join('storage', 'wb_animation_' + competitor_id)
        subprocess.check_output(['mkdir', '-p', new_destination_directory])
        subprocess.check_output(f'mv {destination_directory}/{controller_name}.* {new_destination_directory}', shell=True)
        _cleanup_storage_files(new_destination_directory)

    with open(destination_directory + '/competitors.txt', 'w') as f:
        f.write(updated_competitors)
    subprocess.check_output(f'mv {destination_directory}/competitors.txt competitors.txt', shell=True)

def _replace_one_performance(performances):
    print("TODO: replace the correct performance and animation")
    print(performances)

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


def _remove_competitor_controllers():
    for path in Path('controllers').glob('*'):
        controller = str(path).split('/')[1]
        if controller.startswith('competitor'):
            shutil.rmtree(path)
