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
import sys
import yaml


def load_config(files=['webots.yaml', 'webots.yml']):
    """Load config from webots.yaml located in the repository root."""

    config = None
    for file in files:
      if os.path.isfile(file):
          with open(file, 'r') as f:
              config = yaml.load(f.read(), Loader=yaml.FullLoader) or {}
          break
    if config is None:
        print('Cannot load `webots.yaml`')
        sys.exit(1)
    return config
