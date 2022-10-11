#!/bin/bash

if [ ! -z "${DEBUG}" ]; then
    export GITHUB_REF='/refs/master'
    export GITHUB_ACTOR='cyberbotics'
    export GITHUB_TOKEN='token123'
    export GITHUB_REPOSITORY='cyberbotics/robot-programming-benchmark'
    export BOT_USERNAME='ThomasOliverKimble-bot'
    export BOT_PAT_KEY='token123'
fi

export GITHUB_TOKEN="$1"
export BOT_PAT_KEY="$2"

# Start
python3 -m benchmark_record_action
