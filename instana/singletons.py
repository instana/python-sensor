import os
import sys
import opentracing

from .agent import StandardAgent, AWSLambdaAgent
from .tracer import InstanaTracer
from .recorder import StandardRecorder, AWSLambdaRecorder

agent = None
tracer = None
span_recorder = None

if os.environ.get("INSTANA_ENDPOINT_URL", False):
    agent = AWSLambdaAgent()
    span_recorder = AWSLambdaRecorder(agent)
else:
    agent = StandardAgent()
    span_recorder = StandardRecorder()


# Retrieve the globally configured agent
def get_agent():
    global agent
    return agent


# Set the global agent for the Instana package.  This is used for the
# test suite only currently.
def set_agent(new_agent):
    global agent
    agent = new_agent


# The global OpenTracing compatible tracer used internally by
# this package.
tracer = InstanaTracer(recorder=span_recorder)

if sys.version_info >= (3, 4):
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


# Retrieve the globally configured tracer
def get_tracer():
    global tracer
    return tracer


# Set the global tracer for the Instana package.  This is used for the
# test suite only currently.
def set_tracer(new_tracer):
    global tracer
    tracer = new_tracer
