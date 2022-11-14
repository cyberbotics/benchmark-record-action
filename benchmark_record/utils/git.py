#!/usr/bin/env python3

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

    github_repository = 'https://{}:{}@github.com/{}'.format(
        os.environ['GITHUB_ACTOR'],
        os.environ['INPUT_PUSH_TOKEN'],
        os.environ['GITHUB_REPOSITORY']
    )

    # We push only if there are changes:
    try:
        subprocess.check_output(['git', 'add', '-A'])
        subprocess.check_output(['git', 'diff', '--exit-code', '--cached', './storage'])
    except:
        # If there are changes:
        subprocess.check_output(['git', 'commit', '-m', message], stderr=subprocess.STDOUT)
        
        if not is_debug():
            params = ['git', 'push']
            if force:
                params += ['-f']
            params += [github_repository]
            subprocess.check_output(params)
        else:
            print(f'@ git push {github_repository}')

def clone(repo, path):
    subprocess.check_output(['git', 'clone', repo, path])