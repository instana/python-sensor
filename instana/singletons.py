import sys
import opentracing

from .agent import Agent
from .tracer import InstanaTracer

from distutils.version import LooseVersion


# The Instana Agent which carries along with it a Sensor that collects metrics.
agent = Agent()


# The global OpenTracing compatible tracer used internally by
# this package.
#
# Usage example:
#
# import instana
# instana.tracer.start_span(...)
#
tracer = InstanaTracer()

if sys.version_info >= (3,4):
    from opentracing.scope_managers.asyncio import AsyncioScopeManager
    async_tracer = InstanaTracer(scope_manager=AsyncioScopeManager())

from opentracing.scope_managers.tornado import TornadoScopeManager
tornado_tracer = InstanaTracer(scope_manager=TornadoScopeManager())

# Set ourselves as the tracer.
opentracing.tracer = tracer
