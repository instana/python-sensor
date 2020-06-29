import os
import sys
import pytest
from distutils.version import LooseVersion


collect_ignore_glob = []

# Cassandra and gevent tests are run in dedicated jobs on CircleCI and will
# be run explicitly.  (So always exclude them here)
if "CASSANDRA_TEST" not in os.environ:
    collect_ignore_glob.append("*test_cassandra*")

if "GEVENT_TEST" not in os.environ:
    collect_ignore_glob.append("*test_gevent*")

if LooseVersion(sys.version) < LooseVersion('3.5.3'):
    collect_ignore_glob.append("*test_asynqp*")
    collect_ignore_glob.append("*test_aiohttp*")
    collect_ignore_glob.append("*test_async*")
    collect_ignore_glob.append("*test_tornado*")
    collect_ignore_glob.append("*test_grpc*")

if LooseVersion(sys.version) >= LooseVersion('3.7.0'):
    collect_ignore_glob.append("*test_sudsjurko*")


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
        'tests.frameworks.test_celery'
    }

