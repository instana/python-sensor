#!/usr/bin/env python
# Script to make a new python-sensor release on Github
# Requires the Github CLI to be installed and configured: https://github.com/cli/cli

import os
import sys
import distutils.spawn
from subprocess import check_output

if len(sys.argv) != 2:
    raise ValueError('Please specify the version to release. e.g. "1.27.1"')

if sys.argv[1] in ['-h', '--help']:
    filename = os.path.basename(__file__)
    print("Usage: %s <version number>" % filename)
    print("Exampe: %s 1.27.1" % filename)
    print("")
    print("This will create a release on Github such as:")
    print("https://github.com/instana/python-sensor/releases/tag/v1.27.1")


# Check requirements first
for cmd in ["gh"]:
    if distutils.spawn.find_executable(cmd) is None:
        print("Can't find required tool: %s" % cmd)
        sys.exit(1)

version = sys.argv[1]
semantic_version = 'v' + version
title = version

body = """
This release includes the following fixes & improvements:

*

Available on PyPI:
https://pypi.python.org/pypi/instana/%s
""" % version

response = check_output(["gh", "release", "create", semantic_version,
                         "-d", # draft
                         "-R", "instana/python-sensor",
                         "-t", semantic_version,
                         "-n", body])


print("If there weren't any failures, the draft release is available at:")
print(response.strip().decode())
