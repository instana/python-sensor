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


if "INSTANA_MAGIC" in os.environ:
    pkg_resources.working_set.add_entry("/tmp/instana/python")

__author__ = 'Instana Inc.'
__copyright__ = 'Copyright 2018 Instana Inc.'
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
    if "INSTANA_DEV" in os.environ:
        print("==========================================================")
        print("Instana: Loading...")
        print("==========================================================")


# User configurable EUM API key for instana.helpers.eum_snippet()
# pylint: disable=invalid-name
eum_api_key = ''


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
    # If we're being loaded into an already running process, then delay agent initialization
    t = Timer(3.0, boot_agent)
    t.start()
else:
    boot_agent()
