from __future__ import absolute_import

import os
import boto3
import pytest

from moto import mock_ses

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
def ses(aws_credentials):
    with mock_ses():
        yield boto3.client('ses', region_name='us-east-1')


def test_vanilla_verify_email(ses):
    result = ses.verify_email_identity(EmailAddress='pglombardo+instana299@tuta.io')
    assert result['ResponseMetadata']['HTTPStatusCode'] == 200


def test_verify_email(ses):
    result = None

    with tracer.start_active_span('test'):
        result = ses.verify_email_identity(EmailAddress='pglombardo+instana299@tuta.io')

    assert result['ResponseMetadata']['HTTPStatusCode'] == 200

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

    assert boto_span.data['boto3']['op'] == 'VerifyEmailIdentity'
    assert boto_span.data['boto3']['ep'] == 'https://email.us-east-1.amazonaws.com'
    assert boto_span.data['boto3']['reg'] == 'us-east-1'
    assert boto_span.data['boto3']['payload'] == {'EmailAddress': 'pglombardo+instana299@tuta.io'}
   
    assert boto_span.data['http']['status'] == 200
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://email.us-east-1.amazonaws.com:443/VerifyEmailIdentity'