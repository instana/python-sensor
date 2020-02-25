#!/usr/bin/env python

import os
import glob
import shutil
import time
import distutils.spawn
from subprocess import call

# Check requirements first
for cmd in ["pip", "zip"]:
    if distutils.spawn.find_executable(cmd) is None:
        print("Can't find required tool: %s" % cmd)
        exit(1)

# Determine where this script is running from
this_file_path = os.path.dirname(os.path.realpath(__file__))

# Change directory to the base of the Python sensor repository
os.chdir(this_file_path + "/../")

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

print("===> Uploading zipfile to AWS as a new lambda layer version")
call(["aws", "lambda", "publish-layer-version", "--layer-name", "instana-py-test", "--zip-file", aws_zip_filename,
      "--compatible-runtimes", "python2.7", "python3.6", "python3.7", "python3.8"])

print("Zipfile should be at: ", fq_zip_filename)


