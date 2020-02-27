import os
import sys
import opentracing

from .agent import StandardAgent, AWSLambdaAgent
from .tracer import InstanaTracer
from .recorder import InstanaRecorder, AWSLambdaRecorder


agent = None
span_recorder = None

if os.environ.get("INSTANA_ENDPOINT_URL", False):
    print("Lambda environment")
    agent = AWSLambdaAgent()
    span_recorder = AWSLambdaRecorder(agent)
else:
    print("Standard host environment")
    agent = StandardAgent()
    span_recorder = InstanaRecorder()


# The global OpenTracing compatible tracer used internally by
# this package.
#
# Usage example:
#
# import instana
# instana.tracer.start_span(...)
#
tracer = InstanaTracer(recorder=span_recorder)

if sys.version_info >= (3,4):
    from opentracing.scope_managers.asyncio import AsyncioScopeManager
    async_tracer = InstanaTracer(scope_manager=AsyncioScopeManager(), recorder=span_recorder)


# Mock the tornado tracer until tornado is detected and instrumented first
tornado_tracer = tracer


def setup_tornado_tracer():
    global tornado_tracer
    from opentracing.scope_managers.tornado import TornadoScopeManager
    tornado_tracer = InstanaTracer(scope_manager=TornadoScopeManager(), recorder=span_recorder)


# Set ourselves as the tracer.
opentracing.tracer = tracer
