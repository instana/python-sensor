from __future__ import absolute_import
import os
import opentracing
from .sensor import Sensor
from .tracer import InstanaTracer
from .options import Options

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
__version__ = '0.9.1'
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


# For any given Python process, we only want one sensor as multiple would
# collect/report metrics in duplicate, triplicate etc..
#
# Usage example:
#
# import instana
# instana.global_sensor
#
global_sensor = Sensor(Options())

# The global OpenTracing compatible tracer used internally by
# this package.
#
# Usage example:
#
# import instana
# instana.internal_tracer.start_span(...)
#
internal_tracer = InstanaTracer()

# Set ourselves as the tracer.
opentracing.tracer = internal_tracer

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
    from .instrumentation.django import middleware  # noqa
