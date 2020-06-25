import os
import sys
import pytest
from distutils.version import LooseVersion

collect_ignore = []
collect_ignore.append("pkg/module_py2.py")


# Cassandra and gevent tests are run in dedicated jobs on CircleCI and will
# be run explicitly.  (So always exclude them here)
if "CASSANDRA_TEST" not in os.environ:
    collect_ignore.append("tests/clients/test_cassandra.py")

if "GEVENT_TEST" not in os.environ:
    collect_ignore.append("tests/frameworks/test_gevent.py")

if LooseVersion(sys.version) < LooseVersion('3.5.3'):
    collect_ignore.append("tests/clients/test_asynqp.py")
    collect_ignore.append("tests/clients/test_aiohttp.py")
    collect_ignore.append("tests/clients/test_async.py")
    collect_ignore.append("tests/clients/test_tornado.py")
    collect_ignore.append("tests/clients/test_grpc.py")

if LooseVersion(sys.version) >= LooseVersion('3.7.0'):
    collect_ignore.append("tests/frameworks/test_sudsjurko.py")


@pytest.fixture(scope='session')
def celery_config():
    return {
        'broker_url': 'redis://localhost:6379',
        'result_backend': 'redis://localhost:6379'
    }


@pytest.fixture(scope='session')
def celery_enable_logging():
    return True


@pytest.fixture(scope='session')
def celery_includes():
    return {
        'tests.test_celery'
    }

