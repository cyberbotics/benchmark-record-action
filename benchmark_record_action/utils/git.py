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
import requests
from benchmark_record_action.utils.utils import is_debug


def init():
    username = os.environ['GITHUB_ACTOR']
    user_info = requests.get(f'https://api.github.com/users/{username}').json()

    subprocess.check_output(['git', 'config', '--global', '--add', 'safe.directory', '/github/workspace'])
    subprocess.check_output(['git', 'config', '--global', '--add', 'safe.directory', '/root/repo'])

    result = subprocess.run('git config --list | grep user.name', shell=True, check=False)
    if result.returncode != 0:
        email = '{}+{}@users.noreply.github.com'.format(user_info['id'], username)
        subprocess.check_output(['git', 'config', '--global', 'user.name', user_info['name'] or username])
        subprocess.check_output(['git', 'config', '--global', 'user.email', email])


def push(message='Updated benchmark recordings', force=True):
    init()

    github_repository = 'https://{}:{}@github.com/{}'.format(
        os.environ['GITHUB_ACTOR'],
        os.environ['INPUT_PUSH_TOKEN'],
        os.environ['GITHUB_REPOSITORY']
    )

    subprocess.check_output(['git', 'config', '--global', '--add', 'safe.directory', '/github/workspace'])
    subprocess.check_output(['git', 'add', '-A'])

try:    # can easily return an error, makes debugging easier
        subprocess.check_output(['git', 'commit', '-m', message], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
        
    if not is_debug():
        params = ['git', 'push']
        if force:
            params += ['-f']
        params += [github_repository]
        subprocess.check_output(params)
    else:
        print(f'@ git push {github_repository}')
