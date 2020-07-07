import os
import sys
import opentracing

from .log import logger
from .tracer import InstanaTracer

agent = None
tracer = None
span_recorder = None

if os.environ.get("INSTANA_TEST", False):
    from .agent.test import TestAgent
    from .recorder import StandardRecorder

    agent = TestAgent()
    span_recorder = StandardRecorder()

elif os.environ.get("LAMBDA_HANDLER", False):
    from .agent.aws_lambda import AWSLambdaAgent
    from .recorder import AWSLambdaRecorder

    agent = AWSLambdaAgent()
    span_recorder = AWSLambdaRecorder(agent)

elif os.environ.get("FARGATE", False):
    from .agent.aws_fargate import AWSFargateAgent
    from .recorder import AWSFargateRecorder

    agent = AWSFargateAgent()
    span_recorder = AWSFargateRecorder(agent)
else:
    from .agent.host import HostAgent
    from .recorder import StandardRecorder

    agent = HostAgent()
    span_recorder = StandardRecorder()


def get_agent():
    """
    Retrieve the globally configured agent
    @return: The Instana Agent singleton
    """
    global agent
    return agent


def set_agent(new_agent):
    """
    Set the global agent for the Instana package.  This is used for the
    test suite only currently.

    @param new_agent: agent to replace current singleton
    @return: None
    """
    global agent
    agent = new_agent


# The global OpenTracing compatible tracer used internally by
# this package.
tracer = InstanaTracer(recorder=span_recorder)

if sys.version_info >= (3, 4):
    try:
        from opentracing.scope_managers.asyncio import AsyncioScopeManager
        async_tracer = InstanaTracer(scope_manager=AsyncioScopeManager(), recorder=span_recorder)
    except Exception:
        logger.debug("Error setting up async_tracer:", exc_info=True)


# Mock the tornado tracer until tornado is detected and instrumented first
tornado_tracer = tracer


def setup_tornado_tracer():
    global tornado_tracer
    from opentracing.scope_managers.tornado import TornadoScopeManager
    tornado_tracer = InstanaTracer(scope_manager=TornadoScopeManager(), recorder=span_recorder)


# Set ourselves as the tracer.
opentracing.tracer = tracer


def get_tracer():
    """
    Retrieve the globally configured tracer
    @return: Tracer
    """
    global tracer
    return tracer


def set_tracer(new_tracer):
    """
    Set the global tracer for the Instana package.  This is used for the
    test suite only currently.
    @param new_tracer: The new tracer to replace the singleton
    @return: None
    """
    global tracer
    tracer = new_tracer
