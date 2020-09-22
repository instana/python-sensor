from __future__ import absolute_import

import os
import boto3
import pytest

from moto import mock_sqs

from instana.singletons import tracer
from ...helpers import get_first_span_by_filter

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
    assert boto_span.data['boto3']['ep'] == 'sqs(https://queue.amazonaws.com)'
    assert boto_span.data['boto3']['reg'] == 'us-east-1'

    payload = {'QueueUrl': 'https://queue.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10, 'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}}, 'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
    assert boto_span.data['boto3']['payload'] == repr(payload)