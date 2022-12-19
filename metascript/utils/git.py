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
import requests


def init():
    username = os.environ['GITHUB_ACTOR']
    user_info = requests.get(f'https://api.github.com/users/{username}').json()
    
    if 'id' not in user_info:
        print(user_info)

    subprocess.check_output(
        ['git', 'config', '--global', '--add', 'safe.directory', '/github/workspace'])
    subprocess.check_output(
        ['git', 'config', '--global', '--add', 'safe.directory', '/root/repo'])

    result = subprocess.run(
        'git config --list | grep user.name', shell=True, check=False)
    if result.returncode != 0:
        email = '{}+{}@users.noreply.github.com'.format(
            user_info['id'], username)
        subprocess.check_output(
            ['git', 'config', '--global', 'user.name', user_info['name'] or username])
        subprocess.check_output(
            ['git', 'config', '--global', 'user.email', email])


def push(message='Updated competition recordings', force=True):

    github_repository = 'https://{}:{}@github.com/{}'.format(
        os.environ['GITHUB_ACTOR'],
        os.environ['INPUT_REPO_TOKEN'],
        os.environ['GITHUB_REPOSITORY']
    )
    print(f'GitHub repository: https://github.com/{os.environ["GITHUB_REPOSITORY"]}')
    # We push only if there are changes:
    try:
        print(subprocess.check_output(['git', 'diff', './participants.txt']))
        subprocess.check_output(['git', 'add', '-A'])
        print(subprocess.check_output(['git', 'diff', '--exit-code', '--cached', './storage']))
    except:
        # If there are changes:
        print(subprocess.check_output(['git', 'commit', '-m', message], stderr=subprocess.STDOUT))
        params = ['git', 'push']
        if force:
            params += ['-f']
        params += [github_repository]
        print(subprocess.check_output(params))


def clone(repo, path):
    subprocess.check_output(['git', 'clone', repo, path])
