# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import importlib.util
import os
import sys
from typing import Any, Dict

import pytest
from opentelemetry.context.context import Context
from opentelemetry.trace import set_span_in_context

if importlib.util.find_spec("celery"):
    pytest_plugins = ("celery.contrib.pytest",)


from instana.agent.host import HostAgent
from instana.collector.base import BaseCollector
from instana.recorder import StanRecorder
from instana.span.base_span import BaseSpan
from instana.span.span import InstanaSpan
from instana.span_context import SpanContext
from instana.tracer import InstanaTracerProvider

collect_ignore_glob = [
    "*test_gevent*"
]

# # Cassandra and gevent tests are run in dedicated jobs on CircleCI and will
# # be run explicitly.  (So always exclude them here)
if not os.environ.get("CASSANDRA_TEST"):
    collect_ignore_glob.append("*test_cassandra*")

if not os.environ.get("COUCHBASE_TEST"):
    collect_ignore_glob.append("*test_couchbase*")

# if not os.environ.get("GEVENT_STARLETTE_TEST"):
#     collect_ignore_glob.append("*test_gevent*")
#     collect_ignore_glob.append("*test_starlette*")

if sys.version_info >= (3, 11):
    if not os.environ.get("GOOGLE_CLOUD_TEST"):
        collect_ignore_glob.append("*test_google-cloud*")

if sys.version_info >= (3, 13):
    # TODO: Test Case failures for unknown reason:
    collect_ignore_glob.append("*test_aiohttp_server*")
    collect_ignore_glob.append("*test_celery*")
    collect_ignore_glob.append("*frameworks/test_tornado_server*")

    # Currently there is a runtime incompatibility caused by the library:
    # `undefined symbol: _PyErr_WriteUnraisableMsg`
    collect_ignore_glob.append("*boto3*")

    # Currently there is a runtime incompatibility caused by the library:
    # `undefined symbol: _PyInterpreterState_Get`
    collect_ignore_glob.append("*test_psycopg2*")
    collect_ignore_glob.append("*test_pep0249*")
    collect_ignore_glob.append("*test_sqlalchemy*")

    # Currently not installable dependencies because of 3.13 incompatibilities
    collect_ignore_glob.append("*test_fastapi*")
    collect_ignore_glob.append("*test_google-cloud-pubsub*")
    collect_ignore_glob.append("*test_google-cloud-storage*")
    collect_ignore_glob.append("*test_grpcio*")
    collect_ignore_glob.append("*test_sanic*")


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


def always_true(_: object) -> bool:
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
