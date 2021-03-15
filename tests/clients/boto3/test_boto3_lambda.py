# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import os
import boto3
import pytest

from moto import mock_lambda

from instana.singletons import tracer
from ...helpers import get_first_span_by_filter


@pytest.fixture(scope='function')
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'


@pytest.fixture(scope='function')
def aws_lambda(aws_credentials):
    with mock_lambda():
        yield boto3.client('lambda', region_name='us-east-1')

def setup_method():
    """ Clear all spans before a test run """
    tracer.recorder.clear_spans()

@pytest.mark.skip("Lambda mocking requires docker")
def test_lambda_invoke(aws_lambda):
    result = None

    with tracer.start_active_span('test'):
        result = aws_lambda.invoke(FunctionName='arn:aws:lambda:us-west-1:410797082306:function:CanaryInACoalMine')

    assert result
    assert len(result['Buckets']) == 1
    assert result['Buckets'][0]['Name'] == 'aws_bucket_name'

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

    assert boto_span.data['boto3']['op'] == 'CreateBucket'
    assert boto_span.data['boto3']['ep'] == 'https://s3.amazonaws.com'
    assert boto_span.data['boto3']['reg'] == 'us-east-1'
    assert boto_span.data['boto3']['payload'] == {'Bucket': 'aws_bucket_name'}
    assert boto_span.data['http']['status'] == 200
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://s3.amazonaws.com:443/CreateBucket'
