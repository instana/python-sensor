# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

import os

from opentelemetry import trace

from .autoprofile.profiler import Profiler
from .tracer import InstanaTracerProvider

agent = None
tracer = None
async_tracer = None
profiler = None
span_recorder = None

# Detect the environment where we are running ahead of time
aws_env = os.environ.get("AWS_EXECUTION_ENV", "")
env_is_test = "INSTANA_TEST" in os.environ
env_is_aws_fargate = aws_env == "AWS_ECS_FARGATE"
env_is_aws_eks_fargate = (
    os.environ.get("INSTANA_TRACER_ENVIRONMENT") == "AWS_EKS_FARGATE"
)
env_is_aws_lambda = "AWS_Lambda_" in aws_env
k_service = os.environ.get("K_SERVICE")
k_configuration = os.environ.get("K_CONFIGURATION")
k_revision = os.environ.get("K_REVISION")
instana_endpoint_url = os.environ.get("INSTANA_ENDPOINT_URL")
env_is_google_cloud_run = all(
    (k_service, k_configuration, k_revision, instana_endpoint_url)
)

if env_is_test:
    from .agent.test import TestAgent
    from .recorder import StanRecorder

    agent = TestAgent()
    span_recorder = StanRecorder(agent)
    profiler = Profiler(agent)

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
elif env_is_google_cloud_run:
    from instana.agent.google_cloud_run import GCRAgent
    from instana.recorder import StanRecorder

    agent = GCRAgent(
        service=k_service, configuration=k_configuration, revision=k_revision
    )
    span_recorder = StanRecorder(agent)
elif env_is_aws_eks_fargate:
    from .agent.aws_eks_fargate import EKSFargateAgent
    from .recorder import StanRecorder

    agent = EKSFargateAgent()
    span_recorder = StanRecorder(agent)
else:
    from .agent.host import HostAgent
    from .recorder import StanRecorder

    agent = HostAgent()
    span_recorder = StanRecorder(agent)
    profiler = Profiler(agent)


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


# The global OpenTelemetry compatible tracer used internally by
# this package.
provider = InstanaTracerProvider(recorder=span_recorder)
provider.add_span_processor(agent)

# Sets the global default tracer provider
trace.set_tracer_provider(provider)

# Creates a tracer from the global tracer provider
tracer = trace.get_tracer("instana.tracer")
async_tracer = trace.get_tracer("instana.async.tracer")
tornado_tracer = None


def setup_tornado_tracer():
    global tornado_tracer
    tornado_tracer = trace.get_tracer("instana.tornado.tracer")


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


def get_profiler():
    """
    Retrieve the globally configured profiler
    @return: Profiler
    """
    global profiler
    return profiler


def set_profiler(new_profiler):
    """
    Set the global profiler for the Instana package.  This is used for the
    test suite only currently.
    @param new_profiler: The new profiler to replace the singleton
    @return: None
    """
    global profiler
    profiler = new_profiler
