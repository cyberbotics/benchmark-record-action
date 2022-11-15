#!/usr/bin/env python3

import subprocess
import os
from datetime import datetime
from math import floor

DEFAULT_CONTROLLER = os.environ['DEFAULT_CONTROLLER']

def _generate_animation_recorder_vrml(duration, output, controller_name):
    return (
        f'DEF ANIMATION_RECORDER_SUPERVISOR Robot {{\n'
        f'  name "animation_recorder_supervisor"\n'
        f'  controller "animator"\n'
        f'  controllerArgs [\n'
        f'    "--duration={duration}"\n'
        f'    "--output={output}"\n'
        f'    "--controller={controller_name}"\n'
        f'  ]\n'
        f'  supervisor TRUE\n'
        f'}}\n'
    )

def record_animations(world_config, destination_directory, controller_name):
    # Create temporary directory
    subprocess.check_output(['mkdir', '-p', destination_directory])

    # Temporary file changes*:
    with open(world_config['file'], 'r') as f:
        world_content = f.read()
    updated_file = world_content.replace(f'controller "{DEFAULT_CONTROLLER}"', 'controller "<extern>"')

    animation_recorder_vrml = _generate_animation_recorder_vrml(
        duration = world_config['max-duration'],
        output = destination_directory,
        controller_name = controller_name
    )

    with open(world_config['file'], 'w') as f:
        f.write(updated_file + animation_recorder_vrml)
    
    # Building the Docker containers
    recorder_build = subprocess.Popen(
        [
            "docker", "build",
            "-t", "recorder-webots",
            "-f", "Dockerfile",
            "--build-arg", f"WORLD_PATH={world_config['file']}",
            "."
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )
    _get_realtime_stdout(recorder_build, "Error while building the recorder container")

    controller_build = subprocess.Popen(
        [
            "docker", "build",
            "-t", "controller-docker",
            "-f", f"controllers/{controller_name}/controller_Dockerfile",
            "--build-arg", f"DEFAULT_CONTROLLER={DEFAULT_CONTROLLER}",
            f"controllers/{controller_name}"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )
    _get_realtime_stdout(controller_build, "Error while building the controller container")
    
    # Run Webots container with Popen to read the stdout
    webots_docker = subprocess.Popen(
        [
            "docker", "run", "-t", "--rm", "--init",
            "--mount", f'type=bind,source={os.getcwd()}/tmp/animation,target=/usr/local/webots-project/{destination_directory}',
            "-p", "3005:1234",
            "--env", "CI=true",
            "recorder-webots"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8'
    )

    already_launched_controller = False
    performance = 0
    timeout = False
    
    while webots_docker.poll() is None:
        realtime_output = _print_stdout(webots_docker)
        if not already_launched_controller and "waiting for connection" in realtime_output:
                print("META SCRIPT: Webots ready for controller, launching controller container...")
                subprocess.Popen(
                    ["docker", "run", "--rm", "controller-docker"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
                )
                already_launched_controller = True
        if already_launched_controller and "performance_line:" in realtime_output:
            performance = float(realtime_output.strip().replace("performance_line:", ""))
            break
        elif already_launched_controller and "Controller timeout" in realtime_output:
            timeout = True
            break
    if webots_docker.returncode:
        raise Exception(f"ERROR: Webots container exited with code {webots_docker.returncode}")

    print("Closing the containers...")
    webots_container_id = _get_container_id("recorder-webots")
    if webots_container_id != '':
        # Closing Webots with SIGINT to trigger animation export
        subprocess.run(['/bin/bash', '-c', f'docker exec {webots_container_id} pkill -SIGINT webots-bin'])
    controller_container_id = _get_container_id("controller-docker")
    if controller_container_id != '':
        subprocess.run(['/bin/bash', '-c', f'docker kill {controller_container_id}'])

    # *Restoring temporary file changes
    with open(world_config['file'], 'w') as f:
        f.write(world_content)

    return _get_performance_line(timeout, performance, world_config)

def _get_performance_line(timeout, performance, world_config):
    metric = world_config['metric']
    if not timeout:
        # Benchmark completed normally
        performance_line = _performance_format(performance, metric)
    elif metric != 'time-duration':
        # Benchmark failed: time limit reached
        performance_line = _performance_format(0, metric)
    else:
        # Time-duration benchmark completed with maximum time
        performance_line = _performance_format(world_config['max-duration'], metric)

    return performance_line

def _performance_format(performance, metric):
    if performance == 0:
        performance_string = "failure"
    elif metric == "time-duration" or metric == "time-speed":
        performance_string = _time_convert(performance)
    elif metric ==  "percent":
        performance_string = str(round(performance * 100, 2)) + '%'
    elif metric == "distance":
        performance_string = "{:.3f} m.".format(performance)
    return f"{performance}:{performance_string}:{datetime.today().strftime('%Y-%m-%d')}"

def _time_convert(time):
    minutes = time / 60
    absolute_minutes =  floor(minutes)
    minutes_string = str(absolute_minutes).zfill(2)
    seconds = (minutes - absolute_minutes) * 60
    absolute_seconds =  floor(seconds)
    seconds_string = str(absolute_seconds).zfill(2)
    cs = floor((seconds - absolute_seconds) * 100)
    cs_string = str(cs).zfill(2)
    return minutes_string + "." + seconds_string + "." + cs_string

# function to get the container id of a running container
def _get_container_id(container_name):
    container_id = subprocess.check_output(['docker', 'ps', '-f', f'ancestor={container_name}', '-q']).decode('utf-8').strip()
    return container_id

# function to get the stdout of a Popen process in realtime
def _get_realtime_stdout(process, error_message):
    while process.poll() is None:
        _print_stdout(process)
    if process.returncode != 0:
        raise Exception(error_message)

def _print_stdout(process):
    realtime_output = process.stdout.readline()
    if realtime_output:
        print(realtime_output.strip())
    return realtime_output