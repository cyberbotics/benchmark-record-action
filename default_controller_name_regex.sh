#!/bin/bash

yaml_file=$(<webots.yml)
echo $yaml_file
regex='dockerCompose: theia:webots-project/controllers/(.+)/'
if [[ $yaml_file =~ $regex ]]
then
  ctrl_name="${BASH_REMATCH[1]}"
  echo "$ctrl_name"
else
  ctrl_name="REGEX failed"
  exit 1
fi
echo "DEFAULT_CONTROLLER=$ctrl_name" >> $GITHUB_ENV
