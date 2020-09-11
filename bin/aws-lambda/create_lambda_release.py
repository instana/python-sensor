#!/usr/bin/env python
# Script to make a new AWS Lambda Layer release on Github
# Requires the Github CLI to be installed and configured: https://github.com/cli/cli

import sys
import json
import distutils.spawn
from subprocess import check_output

if len(sys.argv) != 2:
    raise ValueError('Please specify the layer version to release. e.g. "11"')

# Check requirements first
for cmd in ["gh"]:
    if distutils.spawn.find_executable(cmd) is None:
        print("Can't find required tool: %s" % cmd)
        sys.exit(1)

regions = ['ap-northeast-1', 'ap-northeast-2', 'ap-south-1', 'ap-southeast-1', 'ap-southeast-2', 'ca-central-1',
           'eu-central-1', 'eu-north-1', 'eu-west-1', 'eu-west-2', 'eu-west-3', 'sa-east-1', 'us-east-1',
           'us-east-2', 'us-west-1', 'us-west-2']

version = sys.argv[1]
semantic_version = 'v' + version
title = "AWS Lambda Version %s" % semantic_version

body = '| AWS Region | ARN |\n'
body += '| :-- | :-- |\n'
for region in regions:
    body += "| %s | arn:aws:lambda:%s:410797082306:layer:instana-python:%s |\n" % (region, region, version)

response = check_output(["gh", "api", "repos/:owner/:repo/releases", "--method=POST",
                         "-F", ("tag_name=%s" % semantic_version),
                         "-F", "name=%s" % title,
                         "-F", "body=%s" % body])

json_data = json.loads(response)

print("If there weren't any failures, the release is available at:")
print(json_data["html_url"])
