from __future__ import absolute_import

import os
import boto3
import pytest

from moto import mock_s3

from instana.singletons import tracer
from ...helpers import get_first_span_by_filter

pwd = os.path.dirname(os.path.abspath(__file__))
upload_filename = os.path.abspath(pwd + '/../../data/boto3/test_upload_file.jpg')
download_target_filename = os.path.abspath(pwd + '/../../data/boto3/download_target_file.asdf')

def setup_method():
    """ Clear all spans before a test run """
    tracer.recorder.clear_spans()
    os.remove(download_target_filename)


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


def test_vanilla_create_bucket(s3):
    # s3 is a fixture defined above that yields a boto3 s3 client.
    # Feel free to instantiate another boto3 S3 client -- Keep note of the region though.
    s3.create_bucket(Bucket="aws_bucket_name")

    result = s3.list_buckets()
    assert len(result['Buckets']) == 1
    assert result['Buckets'][0]['Name'] == 'aws_bucket_name'


def test_s3_create_bucket(s3):
    result = None
    with tracer.start_active_span('test'):
        result = s3.create_bucket(Bucket="aws_bucket_name")

    result = s3.list_buckets()
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


def test_s3_list_buckets(s3):
    result = None
    with tracer.start_active_span('test'):
        result = s3.list_buckets()

    result = s3.list_buckets()
    assert len(result['Buckets']) == 0
    assert result['ResponseMetadata']['HTTPStatusCode'] is 200

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

    assert boto_span.data['boto3']['op'] == 'ListBuckets'
    assert boto_span.data['boto3']['ep'] == 'https://s3.amazonaws.com'
    assert boto_span.data['boto3']['reg'] == 'us-east-1'
    assert boto_span.data['boto3']['payload'] == {}
    assert boto_span.data['http']['status'] == 200
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://s3.amazonaws.com:443/ListBuckets'

def test_s3_vanilla_upload_file(s3):
    object_name = 'aws_key_name'
    bucket_name = 'aws_bucket_name'

    s3.create_bucket(Bucket=bucket_name)
    result = s3.upload_file(upload_filename, bucket_name, object_name)
    assert result is None

def test_s3_upload_file(s3):
    object_name = 'aws_key_name'
    bucket_name = 'aws_bucket_name'

    s3.create_bucket(Bucket=bucket_name)

    result = None
    with tracer.start_active_span('test'):
        s3.upload_file(upload_filename, bucket_name, object_name)

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

    assert boto_span.data['boto3']['op'] == 'upload_file'
    assert boto_span.data['boto3']['ep'] == 'https://s3.amazonaws.com'
    assert boto_span.data['boto3']['reg'] == 'us-east-1'
    payload = {'Filename': upload_filename, 'Bucket': 'aws_bucket_name', 'Key': 'aws_key_name'}
    assert boto_span.data['boto3']['payload'] == payload
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://s3.amazonaws.com:443/upload_file'

def test_s3_upload_file_obj(s3):
    object_name = 'aws_key_name'
    bucket_name = 'aws_bucket_name'

    s3.create_bucket(Bucket=bucket_name)

    result = None
    with tracer.start_active_span('test'):
        with open(upload_filename, "rb") as fd:
            s3.upload_fileobj(fd, bucket_name, object_name)

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

    assert(boto_span.data['boto3']['op'] == 'upload_fileobj')
    assert(boto_span.data['boto3']['ep'] == 'https://s3.amazonaws.com')
    assert(boto_span.data['boto3']['reg'] == 'us-east-1')
    payload = {'Bucket': 'aws_bucket_name', 'Key': 'aws_key_name'}
    assert boto_span.data['boto3']['payload'] == payload
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://s3.amazonaws.com:443/upload_fileobj'

def test_s3_download_file(s3):
    object_name = 'aws_key_name'
    bucket_name = 'aws_bucket_name'

    s3.create_bucket(Bucket=bucket_name)
    s3.upload_file(upload_filename, bucket_name, object_name)

    result = None
    with tracer.start_active_span('test'):
        s3.download_file(bucket_name, object_name, download_target_filename)

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

    assert(boto_span.data['boto3']['op'] == 'download_file')
    assert(boto_span.data['boto3']['ep'] == 'https://s3.amazonaws.com')
    assert(boto_span.data['boto3']['reg'] == 'us-east-1')
    payload = {'Bucket': 'aws_bucket_name', 'Key': 'aws_key_name', 'Filename': '%s' % download_target_filename}
    assert boto_span.data['boto3']['payload'] == payload
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://s3.amazonaws.com:443/download_file'

def test_s3_download_file_obj(s3):
    object_name = 'aws_key_name'
    bucket_name = 'aws_bucket_name'

    s3.create_bucket(Bucket=bucket_name)
    s3.upload_file(upload_filename, bucket_name, object_name)

    result = None
    with tracer.start_active_span('test'):
        with open(download_target_filename, "wb") as fd:
            s3.download_fileobj(bucket_name, object_name, fd)

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

    assert boto_span.data['boto3']['op'] == 'download_fileobj'
    assert boto_span.data['boto3']['ep'] == 'https://s3.amazonaws.com'
    assert boto_span.data['boto3']['reg'] == 'us-east-1'
    assert boto_span.data['http']['method'] == 'POST'
    assert boto_span.data['http']['url'] == 'https://s3.amazonaws.com:443/download_fileobj'