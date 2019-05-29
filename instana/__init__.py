"""
The Instana package has two core components: the agent and the tracer.

The agent is individual to each python process and handles process metric
collection and reporting.

The tracer upholds the OpenTracing API and is responsible for reporting
span data to Instana.

The following outlines the hierarchy of classes for these two components.

Agent
  Sensor
    Meter

Tracer
  Recorder
"""

from __future__ import absolute_import

import os
import sys
from threading import Timer
import pkg_resources

__author__ = 'Instana Inc.'
__copyright__ = 'Copyright 2019 Instana Inc.'
__credits__ = ['Pavlo Baron', 'Peter Giacomo Lombardo']
__license__ = 'MIT'
__maintainer__ = 'Peter Giacomo Lombardo'
__email__ = 'peter.lombardo@instana.com'

try:
    __version__ = pkg_resources.get_distribution('instana').version
except pkg_resources.DistributionNotFound:
    __version__ = 'unknown'


def load(_):
    """
    Method used to activate the Instana sensor via AUTOWRAPT_BOOTSTRAP
    environment variable.
    """
    if "INSTANA_DEBUG" in os.environ:
        print("Instana: activated via AUTOWRAPT_BOOTSTRAP")


def boot_agent():
    """Initialize the Instana agent and conditionally load auto-instrumentation."""
    # Disable all the unused-import violations in this function
    # pylint: disable=unused-import

    import instana.singletons

    if "INSTANA_DISABLE_AUTO_INSTR" not in os.environ:
        # Import & initialize instrumentation
        if sys.version_info >= (3, 5, 3):
            from .instrumentation import asyncio
            from .instrumentation.aiohttp import client
            from .instrumentation.aiohttp import server
            from .instrumentation import asynqp
        from .instrumentation.tornado import client
        from .instrumentation.tornado import server
        from .instrumentation import logging
        from .instrumentation import mysqlpython
        from .instrumentation import redis
        from .instrumentation import sqlalchemy
        from .instrumentation import sudsjurko
        from .instrumentation import urllib3
        from .instrumentation.django import middleware


if "INSTANA_MAGIC" in os.environ:
    pkg_resources.working_set.add_entry("/tmp/instana/python")

    if "INSTANA_DEBUG" in os.environ:
        print("Instana: activated via AutoTrace")
else:
    if ("INSTANA_DEBUG" in os.environ) and ("AUTOWRAPT_BOOTSTRAP" not in os.environ):
        print("Instana: activated via manual import")

# User configurable EUM API key for instana.helpers.eum_snippet()
# pylint: disable=invalid-name
eum_api_key = ''

# This Python package can be loaded into Python processes one of three ways:
#   1. manual import statement
#   2. autowrapt hook
#   3. dynamically injected remotely
#
# With such magic, we may get pulled into Python processes that we have no interest being in.
# As a safety measure, we maintain a "do not load list" and if this process matches something
# in that list, then we go sit in a corner quietly and don't load anything at all.
do_not_load_list = ["pip", "pip2", "pip3", "pipenv", "docker-compose", "easy_install", "easy_install-2.7",
                    "smtpd.py", "ufw", "unattended-upgrade"]

# There are cases when sys.argv may not be defined at load time.  Seems to happen in embedded Python,
# and some Pipenv installs.  If this is the case, it's best effort.
if hasattr(sys, 'argv') and len(sys.argv) > 0 and (os.path.basename(sys.argv[0]) in do_not_load_list):
    if "INSTANA_DEBUG" in os.environ:
        print("Instana: No use in monitoring this process type (%s).  Will go sit in a corner quietly." % os.path.basename(sys.argv[0]))
else:
    if "INSTANA_MAGIC" in os.environ:
        # If we're being loaded into an already running process, then delay agent initialization
        t = Timer(3.0, boot_agent)
        t.start()
    else:
        boot_agent()
