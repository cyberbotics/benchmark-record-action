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

from benchmark_record_action.utils.webots import load_config
from benchmark_record_action.benchmark import benchmark


def main():
    # Load config
    config = load_config()

    # Continue parsing
    if 'type' not in config or config['type'] != 'benchmark':
        print('You have to specify `type` parameter in `webots.yaml` and set it to `benchmark`')
        return

    # Run benchmark
    benchmark(config)


if __name__ == "__main__":
    main()
