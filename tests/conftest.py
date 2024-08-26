# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import importlib.util
import os
import sys
import pytest

if importlib.util.find_spec("celery"):
    pytest_plugins = ("celery.contrib.pytest",)

# Set our testing flags
os.environ["INSTANA_TEST"] = "true"
# os.environ["INSTANA_DEBUG"] = "true"

# Make sure the instana package is fully loaded
import instana

collect_ignore_glob = []

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
