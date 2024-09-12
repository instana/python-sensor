# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

import os
from typing import TYPE_CHECKING, Type

from opentelemetry import trace

from instana.recorder import StanRecorder
from instana.tracer import InstanaTracerProvider
from instana.autoprofile.profiler import Profiler

if TYPE_CHECKING:
    from instana.agent.base import BaseAgent
    from instana.tracer import InstanaTracer

agent = None
tracer = None
profiler = None
span_recorder = None

# Detect the environment where we are running ahead of time
aws_env = os.environ.get("AWS_EXECUTION_ENV", "")
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

if env_is_aws_lambda:
    from .agent.aws_lambda import AWSLambdaAgent
    from .recorder import StanRecorder

    agent = AWSLambdaAgent()
elif env_is_aws_fargate:
    from instana.agent.aws_fargate import AWSFargateAgent
    agent = AWSFargateAgent()
elif env_is_google_cloud_run:
    from instana.agent.google_cloud_run import GCRAgent
    agent = GCRAgent(
        service=k_service, configuration=k_configuration, revision=k_revision
    )
elif env_is_aws_eks_fargate:
    from instana.agent.aws_eks_fargate import EKSFargateAgent
    agent = EKSFargateAgent()
else:
    from instana.agent.host import HostAgent
    agent = HostAgent()
    profiler = Profiler(agent)
    

if agent:
    span_recorder = StanRecorder(agent)        


def get_agent() -> Type["BaseAgent"]:
    """
    Retrieve the globally configured agent
    @return: The Instana Agent singleton
    """
    global agent
    return agent


def set_agent(new_agent: Type["BaseAgent"]) -> None:
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
provider = InstanaTracerProvider(span_processor=span_recorder, exporter=agent)

# Sets the global default tracer provider
trace.set_tracer_provider(provider)

# Creates a tracer from the global tracer provider
tracer = trace.get_tracer("instana.tracer")


def get_tracer() -> "InstanaTracer":
    """
    Retrieve the globally configured tracer
    @return: Tracer
    """
    global tracer
    return tracer


def set_tracer(new_tracer: "InstanaTracer") -> None:
    """
    Set the global tracer for the Instana package.  This is used for the
    test suite only currently.
    @param new_tracer: The new tracer to replace the singleton
    @return: None
    """
    global tracer
    tracer = new_tracer


def get_profiler() -> Profiler:
    """
    Retrieve the globally configured profiler
    @return: Profiler
    """
    global profiler
    return profiler


def set_profiler(new_profiler: Profiler):
    """
    Set the global profiler for the Instana package.  This is used for the
    test suite only currently.
    @param new_profiler: The new profiler to replace the singleton
    @return: None
    """
    global profiler
    profiler = new_profiler
