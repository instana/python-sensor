# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import importlib.util
import os
import sys

import pytest

if importlib.util.find_spec('celery'):
    pytest_plugins = ("celery.contrib.pytest", )

# Set our testing flags
os.environ["INSTANA_TEST"] = "true"
os.environ["INSTANA_DISABLE_AUTO_INSTR"] = "true"

# TODO: remove all "noqa: E402" from instana package imports and move the
# block of env variables setting to below the imports after finishing the
# migration of instrumentation codes.
from instana.span import BaseSpan, InstanaSpan  # noqa: E402
from instana.span_context import SpanContext  # noqa: E402


collect_ignore_glob = [
    "*autoprofile*",
    "*clients*",
    "*frameworks*",
    "*platforms*",
    "*propagators*",
    "*w3c_trace_context*",
]

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

if sys.version_info >= (3, 12):
    # Currently the dependencies of sanic and aiohttp are not installable on 3.12
    # PyLongObject’ {aka ‘struct _longobject’} has no member named ‘ob_digit’
    collect_ignore_glob.append("*test_sanic*")
    collect_ignore_glob.append("*test_aiohttp*")
    # The asyncio also depends on aiohttp
    collect_ignore_glob.append("*test_asyncio*")


@pytest.fixture(scope="session")
def celery_config():
    return {
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
def span_context(trace_id: int, span_id: int) -> SpanContext:
    return SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
    )


@pytest.fixture
def span(span_context: SpanContext) -> InstanaSpan:
    span_name = "test-span"
    return InstanaSpan(span_name, span_context)


@pytest.fixture
def base_span(span: InstanaSpan) -> BaseSpan:
    return BaseSpan(span, None, "test")
