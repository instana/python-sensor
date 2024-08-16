# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import importlib.util
import os
import sys

import pytest
from opentelemetry.context.context import Context
from opentelemetry.trace import set_span_in_context

if importlib.util.find_spec("celery"):
    pytest_plugins = ("celery.contrib.pytest",)

# Set our testing flags
os.environ["INSTANA_TEST"] = "true"

# TODO: remove all "noqa: E402" from instana package imports and move the
# block of env variables setting to below the imports after finishing the
# migration of instrumentation codes.
from instana.agent.test import TestAgent  # noqa: E402
from instana.recorder import StanRecorder  # noqa: E402
from instana.span.base_span import BaseSpan  # noqa: E402
from instana.span.span import InstanaSpan  # noqa: E402
from instana.span_context import SpanContext  # noqa: E402
from instana.tracer import InstanaTracerProvider  # noqa: E402

# Ignoring tests during OpenTelemetry migration.
collect_ignore_glob = [
    "*autoprofile*",
    # "*clients*",
    # "*frameworks*",
    "*platforms*",
    "*propagators*",
    "*w3c_trace_context*",
]

# TODO: remove the following entries as the migration of the instrumentation
# codes are finalised.
collect_ignore_glob.append("*clients/boto*")
collect_ignore_glob.append("*clients/test_cassandra*")
collect_ignore_glob.append("*clients/test_counchbase*")
collect_ignore_glob.append("*clients/test_google*")
collect_ignore_glob.append("*clients/test_mysql*")
collect_ignore_glob.append("*clients/test_pika*")
collect_ignore_glob.append("*clients/test_psycopg*")
collect_ignore_glob.append("*clients/test_pym*")
collect_ignore_glob.append("*clients/test_redis*")
collect_ignore_glob.append("*clients/test_sql*")

collect_ignore_glob.append("*frameworks/test_aiohttp*")
collect_ignore_glob.append("*frameworks/test_asyncio*")
collect_ignore_glob.append("*frameworks/test_celery*")
collect_ignore_glob.append("*frameworks/test_django*")
collect_ignore_glob.append("*frameworks/test_fastapi*")
collect_ignore_glob.append("*frameworks/test_gevent*")
collect_ignore_glob.append("*frameworks/test_grpcio*")
collect_ignore_glob.append("*frameworks/test_pyramid*")
collect_ignore_glob.append("*frameworks/test_sanic*")
collect_ignore_glob.append("*frameworks/test_starlette*")
collect_ignore_glob.append("*frameworks/test_tornado*")

# Cassandra and gevent tests are run in dedicated jobs on CircleCI and will
# be run explicitly.  (So always exclude them here)
if not os.environ.get("CASSANDRA_TEST"):
    collect_ignore_glob.append("*test_cassandra*")

if not os.environ.get("COUCHBASE_TEST"):
    collect_ignore_glob.append("*test_couchbase*")

if not os.environ.get("GEVENT_STARLETTE_TEST"):
    collect_ignore_glob.append("*test_gevent*")
    collect_ignore_glob.append("*test_starlette*")

# Python 3.10 support is incomplete yet
# TODO: Remove this once we start supporting Tornado >= 6.0
if sys.version_info >= (3, 10):
    collect_ignore_glob.append("*test_tornado*")
    # Furthermore on Python 3.11 the above TC is skipped:
    # tests/opentracing/test_ot_span.py::TestOTSpan::test_stacks
    # TODO: Remove that once we find a workaround or DROP opentracing!

if sys.version_info >= (3, 11):
    if not os.environ.get("GOOGLE_CLOUD_TEST"):
        collect_ignore_glob.append("*test_google-cloud*")

if sys.version_info >= (3, 13):
    # TODO: Test Case failures for unknown reason:
    collect_ignore_glob.append("*test_aiohttp_server*")
    collect_ignore_glob.append("*test_celery*")

    # Currently there is a runtime incompatibility caused by the library:
    # `undefined symbol: _PyErr_WriteUnraisableMsg`
    collect_ignore_glob.append("*boto3*")

    # Currently there is a runtime incompatibility caused by the library:
    # `undefined symbol: _PyInterpreterState_Get`
    collect_ignore_glob.append("*test_psycopg2*")
    collect_ignore_glob.append("*test_sqlalchemy*")

    # Currently the latest version of pyramid depends on the `cgi` module
    # which has been deprecated since Python 3.11 and finally removed in 3.13
    # `ModuleNotFoundError: No module named 'cgi'`
    collect_ignore_glob.append("*test_pyramid*")

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
    rec = StanRecorder(TestAgent())
    rec.THREAD_NAME = "InstanaSpan Recorder Test"
    return rec


@pytest.fixture
def tracer_provider(span_processor: StanRecorder) -> InstanaTracerProvider:
    return InstanaTracerProvider(span_processor=span_processor, exporter=TestAgent())


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
