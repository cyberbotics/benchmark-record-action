#!/bin/bash

yaml_file=$(<webots.yml)
regex='file: worlds/(.+).wbt'
if [[ $yaml_file =~ $regex ]]
then
  world_name="${BASH_REMATCH[1]}"
  echo "$world_name"
  export WORLD_NAME="$world_name"
else
  exit 1
fi
