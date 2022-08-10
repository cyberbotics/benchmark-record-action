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
from glob import glob
from pathlib import Path
import subprocess
from benchmark_record_action.config import RESOURCES_DIRECTORY
import benchmark_record_action.utils.git as git

UINT32_MAX = 4294967295
CHARACTER_SET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-"

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

def get_competitors():
    print(str(Path('').glob('competitors.txt')))

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

