from __future__ import absolute_import
import opentracing
from .sensor import Sensor
from .tracer import InstanaTracer
from .options import Options

# Import & initialize instrumentation
from .instrumentation import urllib3

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
__version__ = '0.7.0'
__maintainer__ = 'Peter Giacomo Lombardo'
__email__ = 'peter.lombardo@instana.com'

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
