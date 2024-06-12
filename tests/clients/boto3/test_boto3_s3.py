# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import unittest

from moto import mock_aws
import boto3

from instana.singletons import tracer, agent
from ...helpers import get_first_span_by_filter

pwd = os.path.dirname(os.path.abspath(__file__))
upload_filename = os.path.abspath(pwd + '/../../data/boto3/test_upload_file.jpg')
download_target_filename = os.path.abspath(pwd + '/../../data/boto3/download_target_file.asdf')


class TestS3(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.mock = mock_aws()
        self.mock.start()
        self.s3 = boto3.client('s3', region_name='us-east-1')

    def tearDown(self):
        # Stop Moto after each test
        self.mock.stop()
        agent.options.allow_exit_as_root = False


    def test_vanilla_create_bucket(self):
        self.s3.create_bucket(Bucket="aws_bucket_name")

        result = self.s3.list_buckets()
        self.assertEqual(1, len(result['Buckets']))
        self.assertEqual(result['Buckets'][0]['Name'], 'aws_bucket_name')


    def test_s3_create_bucket(self):
        with tracer.start_active_span('test'):
            self.s3.create_bucket(Bucket="aws_bucket_name")

        result = self.s3.list_buckets()
        self.assertEqual(1, len(result['Buckets']))
        self.assertEqual(result['Buckets'][0]['Name'], 'aws_bucket_name')

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'CreateBucket')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertDictEqual(boto_span.data['boto3']['payload'], {'Bucket': 'aws_bucket_name'})
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/CreateBucket')


    def test_s3_create_bucket_as_root_exit_span(self):
        agent.options.allow_exit_as_root = True
        self.s3.create_bucket(Bucket="aws_bucket_name")

        agent.options.allow_exit_as_root = False
        result = self.s3.list_buckets()
        self.assertEqual(1, len(result['Buckets']))
        self.assertEqual(result['Buckets'][0]['Name'], 'aws_bucket_name')

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))
        boto_span = spans[0]
        self.assertTrue(boto_span)
        self.assertEqual(boto_span.n, "boto3")
        self.assertIsNone(boto_span.p)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'CreateBucket')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertDictEqual(boto_span.data['boto3']['payload'], {'Bucket': 'aws_bucket_name'})
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/CreateBucket')


    def test_s3_list_buckets(self):
        with tracer.start_active_span('test'):
            result = self.s3.list_buckets()

        self.assertEqual(0, len(result['Buckets']))
        self.assertEqual(result['ResponseMetadata']['HTTPStatusCode'], 200)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'ListBuckets')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertDictEqual(boto_span.data['boto3']['payload'], {})
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/ListBuckets')


    def test_s3_vanilla_upload_file(self):
        object_name = 'aws_key_name'
        bucket_name = 'aws_bucket_name'

        self.s3.create_bucket(Bucket=bucket_name)
        result = self.s3.upload_file(upload_filename, bucket_name, object_name)
        self.assertIsNone(result)


    def test_s3_upload_file(self):
        object_name = 'aws_key_name'
        bucket_name = 'aws_bucket_name'

        self.s3.create_bucket(Bucket=bucket_name)

        with tracer.start_active_span('test'):
            self.s3.upload_file(upload_filename, bucket_name, object_name)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'upload_file')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        payload = {'Filename': upload_filename, 'Bucket': 'aws_bucket_name', 'Key': 'aws_key_name'}
        self.assertDictEqual(boto_span.data['boto3']['payload'], payload)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/upload_file')


    def test_s3_upload_file_obj(self):
        object_name = 'aws_key_name'
        bucket_name = 'aws_bucket_name'

        self.s3.create_bucket(Bucket=bucket_name)

        with tracer.start_active_span('test'):
            with open(upload_filename, "rb") as fd:
                self.s3.upload_fileobj(fd, bucket_name, object_name)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'upload_fileobj')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        payload = {'Bucket': 'aws_bucket_name', 'Key': 'aws_key_name'}
        self.assertDictEqual(boto_span.data['boto3']['payload'], payload)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/upload_fileobj')


    def test_s3_download_file(self):
        object_name = 'aws_key_name'
        bucket_name = 'aws_bucket_name'

        self.s3.create_bucket(Bucket=bucket_name)
        self.s3.upload_file(upload_filename, bucket_name, object_name)

        with tracer.start_active_span('test'):
            self.s3.download_file(bucket_name, object_name, download_target_filename)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'download_file')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        payload = {'Bucket': 'aws_bucket_name', 'Key': 'aws_key_name', 'Filename': '%s' % download_target_filename}
        self.assertDictEqual(boto_span.data['boto3']['payload'], payload)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/download_file')


    def test_s3_download_file_obj(self):
        object_name = 'aws_key_name'
        bucket_name = 'aws_bucket_name'

        self.s3.create_bucket(Bucket=bucket_name)
        self.s3.upload_file(upload_filename, bucket_name, object_name)

        with tracer.start_active_span('test'):
            with open(download_target_filename, "wb") as fd:
                self.s3.download_fileobj(bucket_name, object_name, fd)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'download_fileobj')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/download_fileobj')


    def test_request_header_capture_before_call(self):

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This', 'X-Capture-That']

        # Access the event system on the S3 client
        event_system = self.s3.meta.events

        request_headers = {
                'X-Capture-This': 'this',
                'X-Capture-That': 'that'
            }

        # Create a function that adds custom headers
        def add_custom_header_before_call(params, **kwargs):
            params['headers'].update(request_headers)

        # Register the function to before-call event.
        event_system.register('before-call.s3.CreateBucket', add_custom_header_before_call)

        with tracer.start_active_span('test'):
            self.s3.create_bucket(Bucket="aws_bucket_name")

        result = self.s3.list_buckets()
        self.assertEqual(1, len(result['Buckets']))
        self.assertEqual(result['Buckets'][0]['Name'], 'aws_bucket_name')

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'CreateBucket')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertDictEqual(boto_span.data['boto3']['payload'], {'Bucket': 'aws_bucket_name'})
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/CreateBucket')

        self.assertIn("X-Capture-This", boto_span.data["http"]["header"])
        self.assertEqual("this", boto_span.data["http"]["header"]["X-Capture-This"])
        self.assertIn("X-Capture-That", boto_span.data["http"]["header"])
        self.assertEqual("that", boto_span.data["http"]["header"]["X-Capture-That"])

        agent.options.extra_http_headers = original_extra_http_headers


    def test_request_header_capture_before_sign(self):

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Custom-1', 'X-Custom-2']

        # Access the event system on the S3 client
        event_system = self.s3.meta.events

        request_headers = {
                'X-Custom-1': 'Value1',
                'X-Custom-2': 'Value2'
            }

        # Create a function that adds custom headers
        def add_custom_header_before_sign(request, **kwargs):
            for name, value in request_headers.items():
                request.headers.add_header(name, value)

        # Register the function to before-sign event.
        event_system.register_first('before-sign.s3.CreateBucket', add_custom_header_before_sign)

        with tracer.start_active_span('test'):
            self.s3.create_bucket(Bucket="aws_bucket_name")

        result = self.s3.list_buckets()
        self.assertEqual(1, len(result['Buckets']))
        self.assertEqual(result['Buckets'][0]['Name'], 'aws_bucket_name')

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'CreateBucket')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertDictEqual(boto_span.data['boto3']['payload'], {'Bucket': 'aws_bucket_name'})
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/CreateBucket')

        self.assertIn("X-Custom-1", boto_span.data["http"]["header"])
        self.assertEqual("Value1", boto_span.data["http"]["header"]["X-Custom-1"])
        self.assertIn("X-Custom-2", boto_span.data["http"]["header"])
        self.assertEqual("Value2", boto_span.data["http"]["header"]["X-Custom-2"])

        agent.options.extra_http_headers = original_extra_http_headers


    def test_response_header_capture(self):

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This-Too', 'X-Capture-That-Too']

        # Access the event system on the S3 client
        event_system = self.s3.meta.events

        response_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        # Create a function that sets the custom headers in the after-call event.
        def modify_after_call_args(parsed, **kwargs):
            parsed['ResponseMetadata']['HTTPHeaders'].update(response_headers)

        # Register the function to an event
        event_system.register('after-call.s3.CreateBucket', modify_after_call_args)

        with tracer.start_active_span('test'):
            self.s3.create_bucket(Bucket="aws_bucket_name")

        result = self.s3.list_buckets()
        self.assertEqual(1, len(result['Buckets']))
        self.assertEqual(result['Buckets'][0]['Name'], 'aws_bucket_name')

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(boto_span)

        self.assertEqual(boto_span.t, test_span.t)
        self.assertEqual(boto_span.p, test_span.s)

        self.assertIsNone(test_span.ec)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'CreateBucket')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://s3.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertDictEqual(boto_span.data['boto3']['payload'], {'Bucket': 'aws_bucket_name'})
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://s3.amazonaws.com:443/CreateBucket')

        self.assertIn("X-Capture-This-Too", boto_span.data["http"]["header"])
        self.assertEqual("this too", boto_span.data["http"]["header"]["X-Capture-This-Too"])
        self.assertIn("X-Capture-That-Too", boto_span.data["http"]["header"])
        self.assertEqual("that too", boto_span.data["http"]["header"]["X-Capture-That-Too"])

        agent.options.extra_http_headers = original_extra_http_headers
