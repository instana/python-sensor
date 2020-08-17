import os
import sys
import opentracing

from .log import logger
from .tracer import InstanaTracer

agent = None
tracer = None
span_recorder = None

# Detect the environment where we are running ahead of time
aws_env = os.environ.get("AWS_EXECUTION_ENV", "")
env_is_test = "INSTANA_TEST" in os.environ
env_is_aws_fargate = aws_env == "AWS_ECS_FARGATE"
env_is_aws_lambda = "AWS_Lambda_" in aws_env

if env_is_test:
    from .agent.test import TestAgent
    from .recorder import StanRecorder

    agent = TestAgent()
    span_recorder = StanRecorder(agent)

elif env_is_aws_lambda:
    from .agent.aws_lambda import AWSLambdaAgent
    from .recorder import StanRecorder

    agent = AWSLambdaAgent()
    span_recorder = StanRecorder(agent)

elif env_is_aws_fargate:
    from .agent.aws_fargate import AWSFargateAgent
    from .recorder import StanRecorder

    agent = AWSFargateAgent()
    span_recorder = StanRecorder(agent)

else:
    from .agent.host import HostAgent
    from .recorder import StanRecorder

    agent = HostAgent()
    span_recorder = StanRecorder(agent)


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
