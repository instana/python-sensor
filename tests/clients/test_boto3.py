from __future__ import absolute_import

import os
import boto3
import pytest

from moto import mock_s3, mock_sts, mock_cloudwatch

from instana.singletons import tracer
from ..helpers import get_first_span_by_filter


def setup_method():
    """ Clear all spans before a test run """
    tracer.recorder.clear_spans()


@pytest.fixture(scope='function')
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'


@pytest.fixture(scope='function')
def s3(aws_credentials):
    with mock_s3():
        yield boto3.client('s3', region_name='us-east-1')


@pytest.fixture(scope='function')
def sts(aws_credentials):
    with mock_sts():
        yield boto3.client('sts', region_name='us-east-1')


@pytest.fixture(scope='function')
def cloudwatch(aws_credentials):
    # Disable extra logging for tests
    with mock_cloudwatch():
        yield boto3.client('cloudwatch', region_name='us-east-1')


def test_vanilla_create_bucket(s3):
    # s3 is a fixture defined above that yields a boto3 s3 client.
    # Feel free to instantiate another boto3 S3 client -- Keep note of the region though.
    s3.create_bucket(Bucket="somebucket")

    result = s3.list_buckets()
    assert len(result['Buckets']) == 1
    assert result['Buckets'][0]['Name'] == 'somebucket'


def test_create_bucket(s3):
    result = None
    with tracer.start_active_span('test'):
        result = s3.create_bucket(Bucket="somebucket")

    result = s3.list_buckets()
    assert len(result['Buckets']) == 1
    assert result['Buckets'][0]['Name'] == 'somebucket'

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 2

# def test_apply_async(celery_app, celery_worker):
#     result = None
#     with tracer.start_active_span('test'):
#         result = add.apply_async(args=(4, 5))

#     spans = filter_out_ping_tasks(tracer.recorder.queued_spans())
#     assert len(spans) == 3

#     filter = lambda span: span.n == "sdk"
#     test_span = get_first_span_by_filter(spans, filter)
#     assert(test_span)

#     filter = lambda span: span.n == "celery-client"
#     client_span = get_first_span_by_filter(spans, filter)
#     assert(client_span)

#     filter = lambda span: span.n == "celery-worker"
#     worker_span = get_first_span_by_filter(spans, filter)
#     assert(worker_span)

#     assert(client_span.t == test_span.t)
#     assert(client_span.t == worker_span.t)
#     assert(client_span.p == test_span.s)

#     assert("tests.frameworks.test_celery.add" == client_span.data["celery"]["task"])
#     assert("redis" == client_span.data["celery"]["scheme"])
#     assert("localhost" == client_span.data["celery"]["host"])
#     assert("6379" == client_span.data["celery"]["port"])
#     assert(client_span.data["celery"]["task_id"])
#     assert(client_span.data["celery"]["error"] == None)
#     assert(client_span.ec == None)

#     assert("tests.frameworks.test_celery.add" == worker_span.data["celery"]["task"])
#     assert("redis" == worker_span.data["celery"]["scheme"])
#     assert("localhost" == worker_span.data["celery"]["host"])
#     assert("6379" == worker_span.data["celery"]["port"])
#     assert(worker_span.data["celery"]["task_id"])
#     assert(worker_span.data["celery"]["error"] == None)
#     assert(worker_span.data["celery"]["retry-reason"] == None)
#     assert(worker_span.ec == None)
