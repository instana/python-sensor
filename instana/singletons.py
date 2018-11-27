import opentracing

from .agent import Agent  # noqa
from .tracer import InstanaTracer  # noqa

from opentracing.scope_managers.asyncio import AsyncioScopeManager

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
async_tracer = InstanaTracer(AsyncioScopeManager())

# Set ourselves  as the tracer.
opentracing.tracer = tracer
