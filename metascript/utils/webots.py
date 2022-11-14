#!/usr/bin/env python3

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
