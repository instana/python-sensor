from __future__ import absolute_import

import os
import boto3
import pytest

from moto import mock_secretsmanager

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
def secretsmanager(aws_credentials):
    with mock_secretsmanager():
        yield boto3.client('secretsmanager', region_name='us-east-1')


def test_vanilla_list_secrets(secretsmanager):
    result = secretsmanager.list_secrets(MaxResults=123)
    assert result['SecretList'] == []


def test_get_secret_value(secretsmanager):
    result = None

    secretsmanager.put_secret_value(
        SecretId='Uber_Password',
        SecretBinary=b'password1',
        SecretString='password1',
        VersionStages=[
            'string',
        ]
    )
    
    with tracer.start_active_span('test'):
        result = secretsmanager.get_secret_value(SecretId="Uber_Password")

    assert result['Name'] == 'Uber_Password'

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

    assert boto_span.data['boto3']['op'] == 'GetSecretValue'
    assert boto_span.data['boto3']['ep'] == 'https://secretsmanager.us-east-1.amazonaws.com'
    assert boto_span.data['boto3']['reg'] == 'us-east-1'
    assert 'payload' not in boto_span.data['boto3']
    
    assert boto_span.data['http']['status'] == 200
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://secretsmanager.us-east-1.amazonaws.com:443/GetSecretValue'