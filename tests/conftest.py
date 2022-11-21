# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import sys
import pytest

collect_ignore_glob = []

# Cassandra and gevent tests are run in dedicated jobs on CircleCI and will
# be run explicitly.  (So always exclude them here)
if not os.environ.get("CASSANDRA_TEST" ):
    collect_ignore_glob.append("*test_cassandra*")

if not os.environ.get("COUCHBASE_TEST"):
    collect_ignore_glob.append("*test_couchbase*")

if not os.environ.get("GEVENT_TEST"):
    collect_ignore_glob.append("*test_gevent*")

# Python 3.10 support is incomplete yet
# TODO: Remove this once we start supporting Tornado >= 6.0
# TODO: Remove this once we start supporting moto>=2.0 (impacting boto)
if sys.version_info.minor >= 10:
    collect_ignore_glob.append("*test_tornado*")
    collect_ignore_glob.append("*test_boto3_secretsmanager*")


# Set our testing flags
os.environ["INSTANA_TEST"] = "true"
# os.environ["INSTANA_DEBUG"] = "true"

# Make sure the instana package is fully loaded
import instana


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
