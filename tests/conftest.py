# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import importlib.util
import os
import sys
from typing import Any, Dict

import pytest
from opentelemetry.context.context import Context
from opentelemetry.trace import set_span_in_context
from opentelemetry.trace.span import format_span_id

if importlib.util.find_spec("celery"):
    pytest_plugins = ("celery.contrib.pytest",)


from instana.agent.host import HostAgent
from instana.collector.base import BaseCollector
from instana.fsm import TheMachine
from instana.recorder import StanRecorder
from instana.span.base_span import BaseSpan
from instana.span.span import InstanaSpan
from instana.span_context import SpanContext
from instana.tracer import InstanaTracerProvider
from instana.util.runtime import get_runtime_env_info

collect_ignore_glob = [
    "*test_gevent*",
    "*collector/test_gcr*",
    "*agent/test_google*",
]

# ppc64le and s390x have limitations with some supported libraries.
machine, py_version = get_runtime_env_info()
if machine in ["ppc64le", "s390x"]:
    collect_ignore_glob.extend([
        "*test_google-cloud*",
        "*test_pymongo*",
    ])

    if machine == "ppc64le":
        collect_ignore_glob.append("*test_grpcio*")

# # Cassandra and gevent tests are run in dedicated jobs on CircleCI and will
# # be run explicitly.  (So always exclude them here)
if not os.environ.get("CASSANDRA_TEST"):
    collect_ignore_glob.append("*test_cassandra*")

if not os.environ.get("COUCHBASE_TEST"):
    collect_ignore_glob.append("*test_couchbase*")

if not os.environ.get("GEVENT_STARLETTE_TEST"):
    collect_ignore_glob.extend([
        "*test_gevent*",
        "*test_starlette*",
    ])

if not os.environ.get("KAFKA_TEST"):
    collect_ignore_glob.append("*kafka/test*")

if sys.version_info >= (3, 12):
    # Currently Spyne does not support python > 3.12
    collect_ignore_glob.append("*test_spyne*")


if sys.version_info >= (3, 14):
    collect_ignore_glob.extend([
        # Currently not installable dependencies because of 3.14 incompatibilities
        "*test_fastapi*",
        # aiohttp-server tests failing due to deprecated methods used
        "*test_aiohttp_server*",
        # Currently Sanic does not support python >= 3.14
        "*test_sanic*",
    ])

@pytest.fixture(scope="session")
def celery_config():
    return {
        "broker_connection_retry_on_startup": True,
        "broker_url": "redis://localhost:6379",
        "result_backend": "redis://localhost:6379",
    }


@pytest.fixture(scope="session")
def celery_enable_logging():
    return True


@pytest.fixture(scope="session")
def celery_includes():
    return {"tests.frameworks.test_celery"}


@pytest.fixture
def trace_id() -> int:
    return 1812338823475918251


@pytest.fixture
def span_id() -> int:
    return 6895521157646639861


@pytest.fixture
def hex_trace_id(trace_id: int) -> str:
    # Using format_span_id() to return a 16-byte hexadecimal string, instead of
    # the 32-byte hexadecimal string from format_trace_id().
    return format_span_id(trace_id)


@pytest.fixture
def hex_span_id(span_id: int) -> str:
    return format_span_id(span_id)


@pytest.fixture
def span_processor() -> StanRecorder:
    rec = StanRecorder(HostAgent())
    rec.THREAD_NAME = "InstanaSpan Recorder Test"
    return rec


@pytest.fixture
def tracer_provider(span_processor: StanRecorder) -> InstanaTracerProvider:
    return InstanaTracerProvider(span_processor=span_processor, exporter=HostAgent())


@pytest.fixture
def span_context(trace_id: int, span_id: int) -> SpanContext:
    return SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
    )


@pytest.fixture
def span(span_context: SpanContext, span_processor: StanRecorder) -> InstanaSpan:
    span_name = "test-span"
    return InstanaSpan(span_name, span_context, span_processor)


@pytest.fixture
def base_span(span: InstanaSpan) -> BaseSpan:
    return BaseSpan(span, None)


@pytest.fixture
def context(span: InstanaSpan) -> Context:
    return set_span_in_context(span)


def always_true(_: object, *args: object, **kwargs: object) -> bool:
    return True


# Mocking HostAgent.can_send()
@pytest.fixture(autouse=True)
def can_send(monkeypatch, request) -> None:
    """Return always True for HostAgent.can_send()"""
    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original HostAgent.can_send()
        monkeypatch.setattr(HostAgent, "can_send", HostAgent.can_send)
    else:
        monkeypatch.setattr(HostAgent, "can_send", always_true)


# Mocking HostAgent.get_from_structure()
@pytest.fixture(autouse=True)
def get_from_structure(monkeypatch, request) -> None:
    """
    Retrieves the From data that is reported alongside monitoring data.
    @return: dict()
    """

    def _get_from_structure(_: object) -> Dict[str, Any]:
        return {"e": os.getpid(), "h": "fake"}

    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original HostAgent.get_from_structure()
        monkeypatch.setattr(
            HostAgent, "get_from_structure", HostAgent.get_from_structure
        )
    else:
        monkeypatch.setattr(HostAgent, "get_from_structure", _get_from_structure)


# Mocking BaseCollector.prepare_and_report_data()
@pytest.fixture(autouse=True)
def prepare_and_report_data(monkeypatch, request):
    """Return always True for BaseCollector.prepare_and_report_data()"""
    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original BaseCollector.prepare_and_report_data()
        monkeypatch.setattr(
            BaseCollector,
            "prepare_and_report_data",
            BaseCollector.prepare_and_report_data,
        )
    else:
        monkeypatch.setattr(BaseCollector, "prepare_and_report_data", always_true)


# Mocking HostAgent.is_agent_listening()
@pytest.fixture(autouse=True)
def is_agent_listening(monkeypatch, request) -> None:
    """Always return `True` for `HostAgent.is_agent_listening()`"""
    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original HostAgent.is_agent_listening()
        monkeypatch.setattr(
            HostAgent, "is_agent_listening", HostAgent.is_agent_listening
        )
    else:
        monkeypatch.setattr(HostAgent, "is_agent_listening", always_true)


@pytest.fixture(autouse=True)
def lookup_agent_host(monkeypatch, request) -> None:
    """Always return `True` for `TheMachine.lookup_agent_host()`"""
    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original TheMachine.lookup_agent_host()
        monkeypatch.setattr(
            TheMachine, "lookup_agent_host", TheMachine.lookup_agent_host
        )
    else:
        monkeypatch.setattr(TheMachine, "lookup_agent_host", always_true)


@pytest.fixture(autouse=True)
def announce_sensor(monkeypatch, request) -> None:
    """Always return `True` for `TheMachine.announce_sensor()`"""
    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original TheMachine.announce_sensor()
        monkeypatch.setattr(TheMachine, "announce_sensor", TheMachine.announce_sensor)
    else:
        monkeypatch.setattr(TheMachine, "announce_sensor", always_true)


@pytest.fixture(autouse=True)
def announce(monkeypatch, request) -> None:
    """Always return `True` for `Host.announce()`"""
    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original HostAgent.announce()
        monkeypatch.setattr(HostAgent, "announce", HostAgent.announce)
    else:
        monkeypatch.setattr(HostAgent, "announce", always_true)

# Mocking the import of uwsgi
def _uwsgi_masterpid() -> int:
    return 12345

module = type(sys)("uwsgi")
module.opt = {
    "master": True,
    "lazy-apps": True,
    "enable-threads": True,
}
module.masterpid = _uwsgi_masterpid
sys.modules["uwsgi"] = module
