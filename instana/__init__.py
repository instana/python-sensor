from __future__ import absolute_import

import os
from pkg_resources import get_distribution

"""
The Instana package has two core components: the sensor and the tracer.

The sensor is individual to each python process and handles process metric
collection and reporting.

The tracer upholds the OpenTracing API and is responsible for reporting
span data to Instana.
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


# Optional application wide service name.
# Can be configured via environment variable or via code:
#
# export INSTANA_SERVICE_NAME=myservice
#   or
# instana.service_name = "myservice"
service_name = None

# User configurable EUM API key for instana.helpers.eum_snippet()
eum_api_key = ''

if "INSTANA_SERVICE_NAME" in os.environ:
    service_name = os.environ["INSTANA_SERVICE_NAME"]

if "INSTANA_DISABLE_AUTO_INSTR" not in os.environ:
    # Import & initialize instrumentation
    # noqa: ignore=W0611
    from .instrumentation import urllib3  # noqa
    from .instrumentation import sudsjurko  # noqa
    from .instrumentation import mysqlpython  # noqa
    from .instrumentation.django import middleware  # noqa
