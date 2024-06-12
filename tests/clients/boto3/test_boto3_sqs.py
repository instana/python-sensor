# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import boto3
import unittest
import urllib3

from moto import mock_aws

import tests.apps.flask_app
from instana.singletons import tracer, agent
from ...helpers import get_first_span_by_filter, testenv

pwd = os.path.dirname(os.path.abspath(__file__))


class TestSqs(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.mock = mock_aws()
        self.mock.start()
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        self.http_client = urllib3.PoolManager()

    def tearDown(self):
        # Stop Moto after each test
        self.mock.stop()
        agent.options.allow_exit_as_root = False


    def test_vanilla_create_queue(self):
        result = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '86400'
            })
        self.assertEqual(result['ResponseMetadata']['HTTPStatusCode'], 200)


    def test_send_message(self):
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        self.assertTrue(response['QueueUrl'])
        queue_url = response['QueueUrl']

        with tracer.start_active_span('test'):
            response = self.sqs.send_message(
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

        self.assertTrue(response['MessageId'])

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

        self.assertEqual(boto_span.data['boto3']['op'], 'SendMessage')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://sqs.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        self.assertDictEqual(boto_span.data['boto3']['payload'], payload)

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://sqs.us-east-1.amazonaws.com:443/SendMessage')


    def test_send_message_as_root_exit_span(self):
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        self.assertTrue(response['QueueUrl'])
        agent.options.allow_exit_as_root = True
        queue_url = response['QueueUrl']

        response = self.sqs.send_message(
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

        self.assertTrue(response['MessageId'])

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))
        boto_span = spans[0]
        self.assertTrue(boto_span)
        self.assertEqual(boto_span.n, "boto3")
        self.assertIsNone(boto_span.p)
        self.assertIsNone(boto_span.ec)


        self.assertEqual(boto_span.data['boto3']['op'], 'SendMessage')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://sqs.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        self.assertDictEqual(boto_span.data['boto3']['payload'], payload)

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://sqs.us-east-1.amazonaws.com:443/SendMessage')


    def test_app_boto3_sqs(self):
        with tracer.start_active_span('test'):
            self.http_client.request('GET', testenv["wsgi_server"] + '/boto3/sqs')

        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == "urllib3"
        http_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(http_span)

        filter = lambda span: span.n == "wsgi"
        wsgi_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(wsgi_span)

        filter = lambda span: span.n == "boto3" and span.data['boto3']['op'] == 'CreateQueue'
        bcq_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(bcq_span)

        filter = lambda span: span.n == "boto3" and span.data['boto3']['op'] == 'SendMessage'
        bsm_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(bsm_span)

        self.assertEqual(http_span.t, test_span.t)
        self.assertEqual(http_span.p, test_span.s)

        self.assertEqual(wsgi_span.t, test_span.t)
        self.assertEqual(wsgi_span.p, http_span.s)

        self.assertEqual(bcq_span.t, test_span.t)
        self.assertEqual(bcq_span.p, wsgi_span.s)

        self.assertEqual(bsm_span.t, test_span.t)
        self.assertEqual(bsm_span.p, wsgi_span.s)


    def test_request_header_capture_before_call(self):
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        self.assertTrue(response['QueueUrl'])

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This', 'X-Capture-That']

        # Access the event system on the S3 client
        event_system = self.sqs.meta.events

        request_headers = {
                'X-Capture-This': 'this',
                'X-Capture-That': 'that'
            }

        # Create a function that adds custom headers
        def add_custom_header_before_call(params, **kwargs):
            params['headers'].update(request_headers)

        # Register the function to before-call event.
        event_system.register('before-call.sqs.SendMessage', add_custom_header_before_call)

        queue_url = response['QueueUrl']
        with tracer.start_active_span('test'):
            response = self.sqs.send_message(
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

        self.assertTrue(response['MessageId'])

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

        self.assertEqual(boto_span.data['boto3']['op'], 'SendMessage')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://sqs.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        self.assertDictEqual(boto_span.data['boto3']['payload'], payload)

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://sqs.us-east-1.amazonaws.com:443/SendMessage')

        self.assertIn("X-Capture-This", boto_span.data["http"]["header"])
        self.assertEqual("this", boto_span.data["http"]["header"]["X-Capture-This"])
        self.assertIn("X-Capture-That", boto_span.data["http"]["header"])
        self.assertEqual("that", boto_span.data["http"]["header"]["X-Capture-That"])

        agent.options.extra_http_headers = original_extra_http_headers


    def test_request_header_capture_before_sign(self):
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        self.assertTrue(response['QueueUrl'])

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Custom-1', 'X-Custom-2']

        # Access the event system on the S3 client
        event_system = self.sqs.meta.events

        request_headers = {
                'X-Custom-1': 'Value1',
                'X-Custom-2': 'Value2'
            }

        # Create a function that adds custom headers
        def add_custom_header_before_sign(request, **kwargs):
            for name, value in request_headers.items():
                request.headers.add_header(name, value)

        # Register the function to before-sign event.
        event_system.register_first('before-sign.sqs.SendMessage', add_custom_header_before_sign)

        queue_url = response['QueueUrl']
        with tracer.start_active_span('test'):
            response = self.sqs.send_message(
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

        self.assertTrue(response['MessageId'])

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

        self.assertEqual(boto_span.data['boto3']['op'], 'SendMessage')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://sqs.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        self.assertDictEqual(boto_span.data['boto3']['payload'], payload)

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://sqs.us-east-1.amazonaws.com:443/SendMessage')

        self.assertIn("X-Custom-1", boto_span.data["http"]["header"])
        self.assertEqual("Value1", boto_span.data["http"]["header"]["X-Custom-1"])
        self.assertIn("X-Custom-2", boto_span.data["http"]["header"])
        self.assertEqual("Value2", boto_span.data["http"]["header"]["X-Custom-2"])

        agent.options.extra_http_headers = original_extra_http_headers


    def test_response_header_capture(self):
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        self.assertTrue(response['QueueUrl'])

        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This-Too', 'X-Capture-That-Too']

        # Access the event system on the S3 client
        event_system = self.sqs.meta.events

        response_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        # Create a function that sets the custom headers in the after-call event.
        def modify_after_call_args(parsed, **kwargs):
            parsed['ResponseMetadata']['HTTPHeaders'].update(response_headers)

        # Register the function to an event
        event_system.register('after-call.sqs.SendMessage', modify_after_call_args)

        queue_url = response['QueueUrl']
        with tracer.start_active_span('test'):
            response = self.sqs.send_message(
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

        self.assertTrue(response['MessageId'])

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

        self.assertEqual(boto_span.data['boto3']['op'], 'SendMessage')
        self.assertEqual(boto_span.data['boto3']['ep'], 'https://sqs.us-east-1.amazonaws.com')
        self.assertEqual(boto_span.data['boto3']['reg'], 'us-east-1')

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        self.assertDictEqual(boto_span.data['boto3']['payload'], payload)

        self.assertEqual(boto_span.data['http']['status'], 200)
        self.assertEqual(boto_span.data['http']['method'], 'POST')
        self.assertEqual(boto_span.data['http']['url'], 'https://sqs.us-east-1.amazonaws.com:443/SendMessage')

        self.assertIn("X-Capture-This-Too", boto_span.data["http"]["header"])
        self.assertEqual("this too", boto_span.data["http"]["header"]["X-Capture-This-Too"])
        self.assertIn("X-Capture-That-Too", boto_span.data["http"]["header"])
        self.assertEqual("that too", boto_span.data["http"]["header"]["X-Capture-That-Too"])

        agent.options.extra_http_headers = original_extra_http_headers
