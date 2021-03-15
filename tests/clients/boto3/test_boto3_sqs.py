# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import os
import boto3
import pytest
import urllib3

from moto import mock_sqs

import tests.apps.flask_app
from instana.singletons import tracer
from ...helpers import get_first_span_by_filter, testenv


pwd = os.path.dirname(os.path.abspath(__file__))

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
def http_client():
    yield urllib3.PoolManager()

@pytest.fixture(scope='function')
def sqs(aws_credentials):
    with mock_sqs():
        yield boto3.client('sqs', region_name='us-east-1')


def test_vanilla_create_queue(sqs):
    result = sqs.create_queue(
    QueueName='SQS_QUEUE_NAME',
    Attributes={
        'DelaySeconds': '60',
        'MessageRetentionPeriod': '86400'
    })
    assert result['ResponseMetadata']['HTTPStatusCode'] == 200


def test_send_message(sqs):
    response = None

    # Create the Queue:
    response = sqs.create_queue(
        QueueName='SQS_QUEUE_NAME',
        Attributes={
            'DelaySeconds': '60',
            'MessageRetentionPeriod': '600'
        }
    )
    assert response['QueueUrl']
    queue_url = response['QueueUrl']

    with tracer.start_active_span('test'):
        response = sqs.send_message(
            QueueUrl=queue_url,
            DelaySeconds=10,
            MessageAttributes={
                'Website': {
                    'DataType': 'String',
                    'StringValue': 'https://www.instana.com'
                },
            },
            MessageBody=('Monitor any application, service, or request '
                         'with Instana Application Performance Monitoring')
        )

    assert response['MessageId']

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 2

    filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, filter)
    assert(test_span)

    filter = lambda span: span.n == "boto3"
    boto_span = get_first_span_by_filter(spans, filter)
    assert(boto_span)

    assert(boto_span.t == test_span.t)
    assert(boto_span.p == test_span.s)

    assert(test_span.ec is None)
    assert(boto_span.ec is None)

    assert boto_span.data['boto3']['op'] == 'SendMessage'
    assert boto_span.data['boto3']['ep'] == 'https://queue.amazonaws.com'
    assert boto_span.data['boto3']['reg'] == 'us-east-1'

    payload = {'QueueUrl': 'https://queue.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10, 'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}}, 'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
    assert boto_span.data['boto3']['payload'] == payload
    
    assert boto_span.data['http']['status'] == 200
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://queue.amazonaws.com:443/SendMessage'

@mock_sqs
def test_app_boto3_sqs(http_client):
    with tracer.start_active_span('test'):
        response = http_client.request('GET', testenv["wsgi_server"] + '/boto3/sqs')

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 5

    filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, filter)
    assert test_span

    filter = lambda span: span.n == "urllib3"
    http_span = get_first_span_by_filter(spans, filter)
    assert http_span

    filter = lambda span: span.n == "wsgi"
    wsgi_span = get_first_span_by_filter(spans, filter)
    assert wsgi_span

    filter = lambda span: span.n == "boto3" and span.data['boto3']['op'] == 'CreateQueue'
    bcq_span = get_first_span_by_filter(spans, filter)
    assert bcq_span

    filter = lambda span: span.n == "boto3" and span.data['boto3']['op'] == 'SendMessage'
    bsm_span = get_first_span_by_filter(spans, filter)
    assert bsm_span

    assert http_span.t == test_span.t
    assert http_span.p == test_span.s

    assert wsgi_span.t == test_span.t
    assert wsgi_span.p == http_span.s

    assert bcq_span.t == test_span.t
    assert bcq_span.p == wsgi_span.s

    assert bsm_span.t == test_span.t
    assert bsm_span.p == wsgi_span.s

