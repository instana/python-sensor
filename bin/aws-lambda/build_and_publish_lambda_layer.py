#!/usr/bin/env python

# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import sys
import json
import shutil
import time
import distutils.spawn
from subprocess import call, check_output

# Either -dev or -prod must be specified (and nothing else)
if len(sys.argv) != 2 or (('-dev' not in sys.argv) and ('-prod' not in sys.argv)):
    raise ValueError('Please specify -dev or -prod to indicate which type of layer to build.')

dev_mode = '-dev' in sys.argv

# Disable aws CLI pagination
os.environ["AWS_PAGER"] = ""

# Check requirements first
for cmd in ["pip", "zip"]:
    if distutils.spawn.find_executable(cmd) is None:
        print("Can't find required tool: %s" % cmd)
        exit(1)

# Determine where this script is running from
this_file_path = os.path.dirname(os.path.realpath(__file__))

# Change directory to the base of the Python sensor repository
os.chdir(this_file_path + "/../../")

cwd = os.getcwd()
print("===> Working directory is: %s" % cwd)

# For development, respect or set PYTHONPATH to this repository
local_env = os.environ.copy()
if "PYTHONPATH" not in os.environ:
    local_env["PYTHONPATH"] = os.getcwd()

build_directory = os.getcwd() + '/build/lambda/python'

if os.path.isdir(build_directory):
    print("===> Cleaning build pre-existing directory: %s" % build_directory)
    shutil.rmtree(build_directory)

print("===> Creating new build directory: %s" % build_directory)
os.makedirs(build_directory, exist_ok=True)

print("===> Installing Instana and dependencies into build directory")
call(["pip", "install", "-q", "-U", "-t", os.getcwd() + '/build/lambda/python', "instana"], env=local_env)

print("===> Manually copying in local dev code")
shutil.rmtree(build_directory + "/instana")
shutil.copytree(os.getcwd() + '/instana', build_directory + "/instana")

print("===> Creating Lambda ZIP file")
timestamp = time.strftime("%Y-%m-%d_%H:%M:%S")
zip_filename = "instana-py-layer-%s.zip" % timestamp

os.chdir(os.getcwd() + "/build/lambda/")
call(["zip", "-q", "-r", zip_filename, "./python", "-x", "*.pyc", "./python/pip*", "./python/setuptools*", "./python/wheel*"])

fq_zip_filename = os.getcwd() + '/%s' % zip_filename
aws_zip_filename = "fileb://%s" % fq_zip_filename
print("Zipfile should be at: ", fq_zip_filename)

if dev_mode:
    regions = ['us-west-1']
    LAYER_NAME = "instana-py-dev"
else:
    regions = ['ap-northeast-1', 'ap-northeast-2', 'ap-south-1', 'ap-southeast-1', 'ap-southeast-2', 'ca-central-1',
               'eu-central-1', 'eu-north-1', 'eu-west-1', 'eu-west-2', 'eu-west-3', 'sa-east-1', 'us-east-1',
               'us-east-2', 'us-west-1', 'us-west-2']
    LAYER_NAME = "instana-python"

published = dict()

for region in regions:
    print("===> Uploading layer to AWS %s " % region)
    response = check_output(["aws", "--region", region, "lambda", "publish-layer-version",
                             "--description",
                             "Provides Instana tracing and monitoring of AWS Lambda functions built with Python",
                             "--license-info", "MIT", "--output", "json",
                             "--layer-name", LAYER_NAME, "--zip-file", aws_zip_filename,
                             "--compatible-runtimes", "python3.7", "python3.8", "python3.9", "python3.10"])

    json_data = json.loads(response)
    version = json_data['Version']
    print("===> Uploaded version is %s" % version)

    if dev_mode is False:
        print("===> Making layer public...")
        response = check_output(["aws", "--region", region, "lambda", "add-layer-version-permission",
                                 "--layer-name", LAYER_NAME, "--version-number", str(version),
                                 "--statement-id", "public-permission-all-accounts",
                                 "--principal", "*",
                                 "--action", "lambda:GetLayerVersion",
                                 "--output", "text"])

    published[region] = json_data['LayerVersionArn']


print("===> Published list:")
for key in published.keys():
    print("%s\t%s" % (key, published[key]))
