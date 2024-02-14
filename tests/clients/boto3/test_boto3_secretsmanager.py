# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import boto3
import unittest

# TODO: Remove branching when we drop support for Python 3.7
import sys
if sys.version_info >= (3, 8):
  from moto import mock_aws
else:
  from moto import mock_secretsmanager as mock_aws

from instana.singletons import tracer, agent
from ...helpers import get_first_span_by_filter

pwd = os.path.dirname(os.path.abspath(__file__))

class TestSecretsManager(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.mock = mock_aws()
        self.mock.start()
        self.secretsmanager = boto3.client('secretsmanager', region_name='us-east-1')

    def tearDown(self):
        # Stop Moto after each test
        self.mock.stop()


    def test_vanilla_list_secrets(self):
        result = self.secretsmanager.list_secrets(MaxResults=123)
        self.assertListEqual(result['SecretList'], [])


    def test_get_secret_value(self):
        secret_id = 'Uber_Password'

        response = self.secretsmanager.create_secret(
            Name=secret_id,
            SecretBinary=b'password1',
            SecretString='password1',
        )

        self.assertEqual(response['Name'], secret_id)

        with tracer.start_active_span('test'):
            result = self.secretsmanager.get_secret_value(SecretId=secret_id)

        self.assertEqual(result['Name'], secret_id)

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

        self.assertEqual(boto_span.data['boto3']['op'], 'GetSecretValue')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://secretsmanager.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertNotIn('payload', boto_span.data['boto3'])

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://secretsmanager.us-east-1.amazonaws.com:443/GetSecretValue')


    def test_request_header_capture_before_call(self):
        secret_id = 'Uber_Password'

        response = self.secretsmanager.create_secret(
            Name=secret_id,
            SecretBinary=b'password1',
            SecretString='password1',
        )

        self.assertEqual(response['Name'], secret_id)

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This', 'X-Capture-That']

        # Access the event system on the S3 client
        event_system = self.secretsmanager.meta.events

        request_headers = {
                'X-Capture-This': 'this',
                'X-Capture-That': 'that'
            }

        # Create a function that adds custom headers
        def add_custom_header_before_call(params, **kwargs):
            params['headers'].update(request_headers)

        # Register the function to before-call event.
        event_system.register('before-call.secrets-manager.GetSecretValue', add_custom_header_before_call)

        with tracer.start_active_span('test'):
            result = self.secretsmanager.get_secret_value(SecretId=secret_id)

        self.assertEqual(result['Name'], secret_id)

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

        self.assertEqual(boto_span.data['boto3']['op'], 'GetSecretValue')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://secretsmanager.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertNotIn('payload', boto_span.data['boto3'])

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://secretsmanager.us-east-1.amazonaws.com:443/GetSecretValue')

        self.assertIn("X-Capture-This", boto_span.data["http"]["header"])
        self.assertEqual("this", boto_span.data["http"]["header"]["X-Capture-This"])
        self.assertIn("X-Capture-That", boto_span.data["http"]["header"])
        self.assertEqual("that", boto_span.data["http"]["header"]["X-Capture-That"])
            
        agent.options.extra_http_headers = original_extra_http_headers

    
    def test_request_header_capture_before_sign(self):
        secret_id = 'Uber_Password'

        response = self.secretsmanager.create_secret(
            Name=secret_id,
            SecretBinary=b'password1',
            SecretString='password1',
        )

        self.assertEqual(response['Name'], secret_id)

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Custom-1', 'X-Custom-2']

        # Access the event system on the S3 client
        event_system = self.secretsmanager.meta.events

        request_headers = {
                'X-Custom-1': 'Value1',
                'X-Custom-2': 'Value2'
            }

        # Create a function that adds custom headers
        def add_custom_header_before_sign(request, **kwargs):
            for name, value in request_headers.items():
                request.headers.add_header(name, value)

        # Register the function to before-sign event.
        event_system.register_first('before-sign.secrets-manager.GetSecretValue', add_custom_header_before_sign)

        with tracer.start_active_span('test'):
            result = self.secretsmanager.get_secret_value(SecretId=secret_id)

        self.assertEqual(result['Name'], secret_id)

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

        self.assertEqual(boto_span.data['boto3']['op'], 'GetSecretValue')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://secretsmanager.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertNotIn('payload', boto_span.data['boto3'])

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://secretsmanager.us-east-1.amazonaws.com:443/GetSecretValue')

        self.assertIn("X-Custom-1", boto_span.data["http"]["header"])
        self.assertEqual("Value1", boto_span.data["http"]["header"]["X-Custom-1"])
        self.assertIn("X-Custom-2", boto_span.data["http"]["header"])
        self.assertEqual("Value2", boto_span.data["http"]["header"]["X-Custom-2"])
            
        agent.options.extra_http_headers = original_extra_http_headers


    def test_response_header_capture(self):
        secret_id = 'Uber_Password'

        response = self.secretsmanager.create_secret(
            Name=secret_id,
            SecretBinary=b'password1',
            SecretString='password1',
        )

        self.assertEqual(response['Name'], secret_id)

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This-Too', 'X-Capture-That-Too']

        # Access the event system on the S3 client
        event_system = self.secretsmanager.meta.events
        
        response_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        # Create a function that sets the custom headers in the after-call event.
        def modify_after_call_args(parsed, **kwargs):
            parsed['ResponseMetadata']['HTTPHeaders'].update(response_headers)

        # Register the function to an event
        event_system.register('after-call.secrets-manager.GetSecretValue', modify_after_call_args)

        with tracer.start_active_span('test'):
            result = self.secretsmanager.get_secret_value(SecretId=secret_id)

        self.assertEqual(result['Name'], secret_id)

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

        self.assertEqual(boto_span.data['boto3']['op'], 'GetSecretValue')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://secretsmanager.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')
        self.assertNotIn('payload', boto_span.data['boto3'])

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://secretsmanager.us-east-1.amazonaws.com:443/GetSecretValue')

        self.assertIn("X-Capture-This-Too", boto_span.data["http"]["header"])
        self.assertEqual("this too", boto_span.data["http"]["header"]["X-Capture-This-Too"])
        self.assertIn("X-Capture-That-Too", boto_span.data["http"]["header"])
        self.assertEqual("that too", boto_span.data["http"]["header"]["X-Capture-That-Too"])
            
        agent.options.extra_http_headers = original_extra_http_headers
