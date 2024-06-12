# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import unittest
import json

import boto3
from moto import mock_aws

from instana.singletons import tracer, agent
from ...helpers import get_first_span_by_filter

class TestLambda(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.mock = mock_aws(config={"lambda": {"use_docker": False}})
        self.mock.start()
        self.lambda_region = "us-east-1"
        self.aws_lambda = boto3.client('lambda', region_name=self.lambda_region)
        self.function_name = "myfunc"

    def tearDown(self):
        # Stop Moto after each test
        self.mock.stop()
        agent.options.allow_exit_as_root = False

    def test_lambda_invoke(self):
        with tracer.start_active_span('test'):
            result = self.aws_lambda.invoke(FunctionName=self.function_name, Payload=json.dumps({"message": "success"}))

        self.assertEqual(result["StatusCode"], 200)
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        self.assertIn("message", result_payload)
        self.assertEqual("success", result_payload["message"])

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

        self.assertEqual(boto_span.data['boto3']['op'], 'Invoke')
        endpoint = f'https://lambda.{self.lambda_region}.amazonaws.com'
        self.assertEqual(boto_span.data['boto3']['ep'], endpoint)
        self.assertEqual(boto_span.data['boto3']['reg'], self.lambda_region)
        self.assertIn('FunctionName', boto_span.data['boto3']['payload'])
        self.assertEqual(boto_span.data['boto3']['payload']['FunctionName'], self.function_name)
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], f'{endpoint}:443/Invoke')

    def test_lambda_invoke_as_root_exit_span(self):
        agent.options.allow_exit_as_root = True
        result = self.aws_lambda.invoke(FunctionName=self.function_name, Payload=json.dumps({"message": "success"}))

        self.assertEqual(result["StatusCode"], 200)
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        self.assertIn("message", result_payload)
        self.assertEqual("success", result_payload["message"])

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))
        boto_span = spans[0]
        self.assertTrue(boto_span)
        self.assertEqual(boto_span.n, "boto3")
        self.assertIsNone(boto_span.p)
        self.assertIsNone(boto_span.ec)

        self.assertEqual(boto_span.data['boto3']['op'], 'Invoke')
        endpoint = f'https://lambda.{self.lambda_region}.amazonaws.com'
        self.assertEqual(boto_span.data['boto3']['ep'], endpoint)
        self.assertEqual(boto_span.data['boto3']['reg'], self.lambda_region)
        self.assertIn('FunctionName', boto_span.data['boto3']['payload'])
        self.assertEqual(boto_span.data['boto3']['payload']['FunctionName'], self.function_name)
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], f'{endpoint}:443/Invoke')

    def test_request_header_capture_before_call(self):
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This', 'X-Capture-That']

        # Access the event system on the S3 client
        event_system = self.aws_lambda.meta.events

        request_headers = {
                'X-Capture-This': 'this',
                'X-Capture-That': 'that'
            }

        # Create a function that adds custom headers
        def add_custom_header_before_call(params, **kwargs):
            params['headers'].update(request_headers)

        # Register the function to before-call event.
        event_system.register('before-call.lambda.Invoke', add_custom_header_before_call)

        with tracer.start_active_span('test'):
            result = self.aws_lambda.invoke(FunctionName=self.function_name, Payload=json.dumps({"message": "success"}))

        self.assertEqual(result["StatusCode"], 200)
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        self.assertIn("message", result_payload)
        self.assertEqual("success", result_payload["message"])

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

        self.assertEqual(boto_span.data['boto3']['op'], 'Invoke')
        endpoint = f'https://lambda.{self.lambda_region}.amazonaws.com'
        self.assertEqual(boto_span.data['boto3']['ep'], endpoint)
        self.assertEqual(boto_span.data['boto3']['reg'], self.lambda_region)
        self.assertIn('FunctionName', boto_span.data['boto3']['payload'])
        self.assertEqual(boto_span.data['boto3']['payload']['FunctionName'], self.function_name)
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], f'{endpoint}:443/Invoke')

        self.assertIn("X-Capture-This", boto_span.data["http"]["header"])
        self.assertEqual("this", boto_span.data["http"]["header"]["X-Capture-This"])
        self.assertIn("X-Capture-That", boto_span.data["http"]["header"])
        self.assertEqual("that", boto_span.data["http"]["header"]["X-Capture-That"])

        agent.options.extra_http_headers = original_extra_http_headers


    def test_request_header_capture_before_sign(self):
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Custom-1', 'X-Custom-2']

        # Access the event system on the S3 client
        event_system = self.aws_lambda.meta.events

        request_headers = {
                'X-Custom-1': 'Value1',
                'X-Custom-2': 'Value2'
            }

        # Create a function that adds custom headers
        def add_custom_header_before_sign(request, **kwargs):
            for name, value in request_headers.items():
                request.headers.add_header(name, value)

        # Register the function to before-sign event.
        event_system.register_first('before-sign.lambda.Invoke', add_custom_header_before_sign)

        with tracer.start_active_span('test'):
            result = self.aws_lambda.invoke(FunctionName=self.function_name, Payload=json.dumps({"message": "success"}))

        self.assertEqual(result["StatusCode"], 200)
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        self.assertIn("message", result_payload)
        self.assertEqual("success", result_payload["message"])

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

        self.assertEqual(boto_span.data['boto3']['op'], 'Invoke')
        endpoint = f'https://lambda.{self.lambda_region}.amazonaws.com'
        self.assertEqual(boto_span.data['boto3']['ep'], endpoint)
        self.assertEqual(boto_span.data['boto3']['reg'], self.lambda_region)
        self.assertIn('FunctionName', boto_span.data['boto3']['payload'])
        self.assertEqual(boto_span.data['boto3']['payload']['FunctionName'], self.function_name)
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], f'{endpoint}:443/Invoke')

        self.assertIn("X-Custom-1", boto_span.data["http"]["header"])
        self.assertEqual("Value1", boto_span.data["http"]["header"]["X-Custom-1"])
        self.assertIn("X-Custom-2", boto_span.data["http"]["header"])
        self.assertEqual("Value2", boto_span.data["http"]["header"]["X-Custom-2"])

        agent.options.extra_http_headers = original_extra_http_headers


    def test_response_header_capture(self):
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This-Too', 'X-Capture-That-Too']

        # Access the event system on the S3 client
        event_system = self.aws_lambda.meta.events

        response_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        # Create a function that sets the custom headers in the after-call event.
        def modify_after_call_args(parsed, **kwargs):
            parsed['ResponseMetadata']['HTTPHeaders'].update(response_headers)

        # Register the function to an event
        event_system.register('after-call.lambda.Invoke', modify_after_call_args)

        with tracer.start_active_span('test'):
            result = self.aws_lambda.invoke(FunctionName=self.function_name, Payload=json.dumps({"message": "success"}))

        self.assertEqual(result["StatusCode"], 200)
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        self.assertIn("message", result_payload)
        self.assertEqual("success", result_payload["message"])

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

        self.assertEqual(boto_span.data['boto3']['op'], 'Invoke')
        endpoint = f'https://lambda.{self.lambda_region}.amazonaws.com'
        self.assertEqual(boto_span.data['boto3']['ep'], endpoint)
        self.assertEqual(boto_span.data['boto3']['reg'], self.lambda_region)
        self.assertIn('FunctionName', boto_span.data['boto3']['payload'])
        self.assertEqual(boto_span.data['boto3']['payload']['FunctionName'], self.function_name)
        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], f'{endpoint}:443/Invoke')

        self.assertIn("X-Capture-This-Too", boto_span.data["http"]["header"])
        self.assertEqual("this too", boto_span.data["http"]["header"]["X-Capture-This-Too"])
        self.assertIn("X-Capture-That-Too", boto_span.data["http"]["header"])
        self.assertEqual("that too", boto_span.data["http"]["header"]["X-Capture-That-Too"])

        agent.options.extra_http_headers = original_extra_http_headers
