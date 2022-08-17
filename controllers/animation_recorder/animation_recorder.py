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

import argparse
import os
from glob import glob
from pathlib import Path
from datetime import datetime
from controller import Supervisor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=float, default=120, help='Duration of the animation in seconds')
    parser.add_argument('--output', default='../../animation/index.html', help='Path at which the animation will be saved')
    parser.add_argument('--controllers', default="['<generic>']", help='List of controllers to run')
    args = parser.parse_args()

    robot = Supervisor()

    rankings_output = os.path.join(args.output)

    for controller in list(args.controllers[2:-2].split("', '")):
        timestep = int(robot.getBasicTimeStep())
        receiver = robot.getDevice('receiver')
        receiver.enable(timestep)

        benchmark_robot = robot.getFromDef('BENCHMARK_ROBOT')
        benchmark_robot.getField('controller').setSFString(controller)

        animations_output = os.path.join(args.output, controller + '.html')

        robot.step(timestep)
        robot.animationStartRecording(animations_output)

        step_i = 0
        done = False
        n_steps = (1000 * args.duration) / robot.getBasicTimeStep()
        while not done and robot.step(timestep) != -1 and step_i < n_steps:
            step_i += 1
            if receiver.getQueueLength() > 0:
                if receiver.getData().decode('utf-8') == 'done':
                    done = True
                receiver.nextPacket()

        if done:
            for _ in range(50):
                robot.step(timestep)
        robot.animationStopRecording()

        if done:
            message = "Benchmark completed."
            competitor_id = controller.split('_')[1]
            performance = '0.8834'
            performance_string = '88%'
            date = datetime.today().strftime('%Y-%m-%d')
            ranking = competitor_id + ':' + performance + ':' + performance_string + ':' + date
            with open('ranking.txt', 'a') as f:
                f.write(ranking + '\n')
        else:
            message = "Time limit reached."
        print(message, 'The animation has been saved.')

        robot.simulationReset()

        robot.getFromDef("BENCHMARK_SUPERVISOR").restartController()

    if Path('ranking.txt').exists():
        with open('ranking.txt', 'r') as f:
            for ranking in f.readlines():
                print("RANKING:", ranking)

    for _ in range(10):
        robot.step(timestep)
    robot.simulationQuit(0)


if __name__ == '__main__':
    main()
