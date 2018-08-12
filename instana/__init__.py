from __future__ import absolute_import

import os
from pkg_resources import get_distribution

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

__author__ = 'Instana Inc.'
__copyright__ = 'Copyright 2017 Instana Inc.'
__credits__ = ['Pavlo Baron', 'Peter Giacomo Lombardo']
__license__ = 'MIT'
__version__ = get_distribution('instana').version
__maintainer__ = 'Peter Giacomo Lombardo'
__email__ = 'peter.lombardo@instana.com'


def load(module):
    """
    Method used to activate the Instana sensor via AUTOWRAPT_BOOTSTRAP
    environment variable.
    """
    if "INSTANA_DEV" in os.environ:
        print("==========================================================")
        print("Instana: Loading...")
        print("==========================================================")


# User configurable EUM API key for instana.helpers.eum_snippet()
eum_api_key = ''

import instana.singletons #noqa

if "INSTANA_DISABLE_AUTO_INSTR" not in os.environ:
    # Import & initialize instrumentation
    from .instrumentation import urllib3  # noqa
    from .instrumentation import sudsjurko  # noqa
    from .instrumentation import mysqlpython  # noqa
    from .instrumentation.django import middleware  # noqa
