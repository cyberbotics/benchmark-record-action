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

import argparse
import time
from controller import Supervisor

CONTROLLER_WAITING_TIME = 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=float, default=30,
                        help='Duration of the animation in seconds')
    parser.add_argument('--output', default='storage',
                        help='Path at which the animation will be saved')
    parser.add_argument('--controller', default="animation_0",
                        help='Name of the default controller')
    args = parser.parse_args()

    supervisor = Supervisor()
    timestep = int(supervisor.getBasicTimeStep())

    # Wait for the controller to connect and start the animation
    supervisor.simulationSetMode(supervisor.SIMULATION_MODE_PAUSE)
    time.sleep(CONTROLLER_WAITING_TIME)
    supervisor.simulationSetMode(supervisor.SIMULATION_MODE_REAL_TIME)
    supervisor.animationStartRecording(
        f"../../{args.output}/{args.controller}.html")

    # Time out detection loop
    step_max = 1000 * args.duration / timestep
    step_counter = 0

    while supervisor.step(timestep) != -1:
        # Stops the simulation if the controller takes too much time
        step_counter += 1
        if step_counter >= step_max:
            break

    # If the time is up, stop recording and signal script to close Webots
    supervisor.animationStopRecording()
    print("Controller timeout")


if __name__ == '__main__':
    main()
