# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import boto3
import pytest
import urllib3
from typing import Generator

from moto import mock_aws

import tests.apps.flask_app
from instana.singletons import tracer, agent
from tests.helpers import get_first_span_by_filter, testenv

pwd = os.path.dirname(os.path.abspath(__file__))


class TestSqs:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """ Setup and Teardown """
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.mock = mock_aws()
        self.mock.start()
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        self.http_client = urllib3.PoolManager()
        yield
        # Stop Moto after each test
        self.mock.stop()
        agent.options.allow_exit_as_root = False


    def test_vanilla_create_queue(self) -> None:
        result = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '86400'
            })
        assert result['ResponseMetadata']['HTTPStatusCode'] == 200


    def test_send_message(self) -> None:
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        assert response['QueueUrl']
        queue_url = response['QueueUrl']

        with tracer.start_as_current_span("test"):
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

        assert response['MessageId']

        spans = self.recorder.queued_spans()
        assert 2 == len(spans)

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert test_span.ec is None

        assert boto_span.data['boto3']['op'] == 'SendMessage'
        assert boto_span.data['boto3']['ep'] == 'https://sqs.us-east-1.amazonaws.com'
        assert boto_span.data['boto3']['reg'] == 'us-east-1'

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        assert boto_span.data['boto3']['payload'] == payload

        assert boto_span.data['http']['status'] == 200
        assert boto_span.data['http']['method'] == 'POST'
        assert boto_span.data['http']['url'] == 'https://sqs.us-east-1.amazonaws.com:443/SendMessage'


    def test_send_message_as_root_exit_span(self) -> None:
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        assert response['QueueUrl']
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

        assert response['MessageId']

        spans = self.recorder.queued_spans()
        assert 1 == len(spans)
        boto_span = spans[0]
        assert boto_span
        assert boto_span.n == "boto3"
        assert boto_span.p is None
        assert boto_span.ec is None


        assert boto_span.data['boto3']['op'] == 'SendMessage'
        assert boto_span.data['boto3']['ep'] == 'https://sqs.us-east-1.amazonaws.com'
        assert boto_span.data['boto3']['reg'] == 'us-east-1'

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        assert boto_span.data['boto3']['payload'] == payload

        assert boto_span.data['http']['status'] == 200
        assert boto_span.data['http']['method'] == 'POST'
        assert boto_span.data['http']['url'] == 'https://sqs.us-east-1.amazonaws.com:443/SendMessage'


    def test_app_boto3_sqs(self) -> None:
        with tracer.start_as_current_span("test"):
            self.http_client.request('GET', testenv["flask_server"] + '/boto3/sqs')

        spans = self.recorder.queued_spans()
        assert 5 == len(spans)

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


    def test_request_header_capture_before_call(self) -> None:
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        assert response['QueueUrl']

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
        with tracer.start_as_current_span("test"):
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

        assert response['MessageId']

        spans = self.recorder.queued_spans()
        assert 2 == len(spans)

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert test_span.ec is None

        assert boto_span.data['boto3']['op'] == 'SendMessage'
        assert boto_span.data['boto3']['ep'] == 'https://sqs.us-east-1.amazonaws.com'
        assert boto_span.data['boto3']['reg'] == 'us-east-1'

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        assert boto_span.data['boto3']['payload'] == payload

        assert boto_span.data['http']['status'] == 200
        assert boto_span.data['http']['method'] == 'POST'
        assert boto_span.data['http']['url'] == 'https://sqs.us-east-1.amazonaws.com:443/SendMessage'

        assert "X-Capture-This" in boto_span.data["http"]["header"]
        assert "this" == boto_span.data["http"]["header"]["X-Capture-This"]
        assert "X-Capture-That" in boto_span.data["http"]["header"]
        assert "that" == boto_span.data["http"]["header"]["X-Capture-That"]

        agent.options.extra_http_headers = original_extra_http_headers


    def test_request_header_capture_before_sign(self) -> None:
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        assert response['QueueUrl']

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
        with tracer.start_as_current_span("test"):
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

        assert response['MessageId']

        spans = self.recorder.queued_spans()
        assert 2 == len(spans)

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert test_span.ec is None

        assert boto_span.data['boto3']['op'] == 'SendMessage'
        assert boto_span.data['boto3']['ep'] == 'https://sqs.us-east-1.amazonaws.com'
        assert boto_span.data['boto3']['reg'] == 'us-east-1'

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        assert boto_span.data['boto3']['payload'] == payload

        assert boto_span.data['http']['status'] == 200
        assert boto_span.data['http']['method'] == 'POST'
        assert boto_span.data['http']['url'] == 'https://sqs.us-east-1.amazonaws.com:443/SendMessage'

        assert "X-Custom-1" in boto_span.data["http"]["header"]
        assert "Value1" == boto_span.data["http"]["header"]["X-Custom-1"]
        assert "X-Custom-2" in boto_span.data["http"]["header"]
        assert "Value2" == boto_span.data["http"]["header"]["X-Custom-2"]

        agent.options.extra_http_headers = original_extra_http_headers


    def test_response_header_capture(self) -> None:
        # Create the Queue:
        response = self.sqs.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        assert response['QueueUrl']

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
        with tracer.start_as_current_span("test"):
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

        assert response['MessageId']

        spans = self.recorder.queued_spans()
        assert 2 == len(spans)

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert test_span.ec is None

        assert boto_span.data['boto3']['op'] == 'SendMessage'
        assert boto_span.data['boto3']['ep'] == 'https://sqs.us-east-1.amazonaws.com'
        assert boto_span.data['boto3']['reg'] == 'us-east-1'

        payload = {'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/SQS_QUEUE_NAME', 'DelaySeconds': 10,
                'MessageAttributes': {'Website': {'DataType': 'String', 'StringValue': 'https://www.instana.com'}},
                'MessageBody': 'Monitor any application, service, or request with Instana Application Performance Monitoring'}
        assert boto_span.data['boto3']['payload'] == payload

        assert boto_span.data['http']['status'] == 200
        assert boto_span.data['http']['method'] == 'POST'
        assert boto_span.data['http']['url'] == 'https://sqs.us-east-1.amazonaws.com:443/SendMessage'

        assert "X-Capture-This-Too" in boto_span.data["http"]["header"]
        assert "this too" == boto_span.data["http"]["header"]["X-Capture-This-Too"]
        assert "X-Capture-That-Too" in boto_span.data["http"]["header"]
        assert "that too" == boto_span.data["http"]["header"]["X-Capture-That-Too"]

        agent.options.extra_http_headers = original_extra_http_headers
