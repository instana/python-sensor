# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import pytest
import json
from typing import Generator
import boto3
from moto import mock_aws

from instana.singletons import tracer, agent
from tests.helpers import get_first_span_by_filter


class TestLambda:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup and Teardown"""
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.mock = mock_aws(config={"lambda": {"use_docker": False}})
        self.mock.start()
        self.lambda_region = "us-east-1"
        self.aws_lambda = boto3.client("lambda", region_name=self.lambda_region)
        self.function_name = "myfunc"
        yield
        # Stop Moto after each test
        self.mock.stop()
        agent.options.allow_exit_as_root = False

    def test_lambda_invoke(self) -> None:
        with tracer.start_as_current_span("test"):
            result = self.aws_lambda.invoke(
                FunctionName=self.function_name,
                Payload=json.dumps({"message": "success"}),
            )

        assert result["StatusCode"] == 200
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        assert "message" in result_payload
        assert result_payload["message"] == "success"

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "Invoke"
        endpoint = f"https://lambda.{self.lambda_region}.amazonaws.com"
        assert boto_span.data["boto3"]["ep"] == endpoint
        assert boto_span.data["boto3"]["reg"] == self.lambda_region
        assert "FunctionName" in boto_span.data["boto3"]["payload"]
        assert boto_span.data["boto3"]["payload"]["FunctionName"] == self.function_name
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert boto_span.data["http"]["url"] == f"{endpoint}:443/Invoke"

    def test_lambda_invoke_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        result = self.aws_lambda.invoke(
            FunctionName=self.function_name, Payload=json.dumps({"message": "success"})
        )

        assert result["StatusCode"] == 200
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        assert "message" in result_payload
        assert result_payload["message"] == "success"

        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        boto_span = spans[0]
        assert boto_span
        assert boto_span.n == "boto3"
        assert not boto_span.p
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "Invoke"
        endpoint = f"https://lambda.{self.lambda_region}.amazonaws.com"
        assert boto_span.data["boto3"]["ep"] == endpoint
        assert boto_span.data["boto3"]["reg"] == self.lambda_region
        assert "FunctionName" in boto_span.data["boto3"]["payload"]
        assert boto_span.data["boto3"]["payload"]["FunctionName"] == self.function_name
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert boto_span.data["http"]["url"] == f"{endpoint}:443/Invoke"

    def test_request_header_capture_before_call(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        # Access the event system on the S3 client
        event_system = self.aws_lambda.meta.events

        request_headers = {"X-Capture-This": "this", "X-Capture-That": "that"}

        # Create a function that adds custom headers
        def add_custom_header_before_call(params, **kwargs):
            params["headers"].update(request_headers)

        # Register the function to before-call event.
        event_system.register(
            "before-call.lambda.Invoke", add_custom_header_before_call
        )

        with tracer.start_as_current_span("test"):
            result = self.aws_lambda.invoke(
                FunctionName=self.function_name,
                Payload=json.dumps({"message": "success"}),
            )

        assert result["StatusCode"] == 200
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        assert "message" in result_payload
        assert result_payload["message"] == "success"

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "Invoke"
        endpoint = f"https://lambda.{self.lambda_region}.amazonaws.com"
        assert boto_span.data["boto3"]["ep"] == endpoint
        assert boto_span.data["boto3"]["reg"] == self.lambda_region
        assert "FunctionName" in boto_span.data["boto3"]["payload"]
        assert boto_span.data["boto3"]["payload"]["FunctionName"] == self.function_name
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert boto_span.data["http"]["url"] == f"{endpoint}:443/Invoke"

        assert "X-Capture-This" in boto_span.data["http"]["header"]
        assert boto_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert "X-Capture-That" in boto_span.data["http"]["header"]
        assert boto_span.data["http"]["header"]["X-Capture-That"] == "that"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_request_header_capture_before_sign(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Custom-1", "X-Custom-2"]

        # Access the event system on the S3 client
        event_system = self.aws_lambda.meta.events

        request_headers = {"X-Custom-1": "Value1", "X-Custom-2": "Value2"}

        # Create a function that adds custom headers
        def add_custom_header_before_sign(request, **kwargs):
            for name, value in request_headers.items():
                request.headers.add_header(name, value)

        # Register the function to before-sign event.
        event_system.register_first(
            "before-sign.lambda.Invoke", add_custom_header_before_sign
        )

        with tracer.start_as_current_span("test"):
            result = self.aws_lambda.invoke(
                FunctionName=self.function_name,
                Payload=json.dumps({"message": "success"}),
            )

        assert result["StatusCode"] == 200
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        assert "message" in result_payload
        assert result_payload["message"] == "success"

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "Invoke"
        endpoint = f"https://lambda.{self.lambda_region}.amazonaws.com"
        assert boto_span.data["boto3"]["ep"] == endpoint
        assert boto_span.data["boto3"]["reg"] == self.lambda_region
        assert "FunctionName" in boto_span.data["boto3"]["payload"]
        assert boto_span.data["boto3"]["payload"]["FunctionName"] == self.function_name
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert boto_span.data["http"]["url"] == f"{endpoint}:443/Invoke"

        assert "X-Custom-1" in boto_span.data["http"]["header"]
        assert boto_span.data["http"]["header"]["X-Custom-1"] == "Value1"
        assert "X-Custom-2" in boto_span.data["http"]["header"]
        assert boto_span.data["http"]["header"]["X-Custom-2"] == "Value2"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_response_header_capture(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        # Access the event system on the S3 client
        event_system = self.aws_lambda.meta.events

        response_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        # Create a function that sets the custom headers in the after-call event.
        def modify_after_call_args(parsed, **kwargs):
            parsed["ResponseMetadata"]["HTTPHeaders"].update(response_headers)

        # Register the function to an event
        event_system.register("after-call.lambda.Invoke", modify_after_call_args)

        with tracer.start_as_current_span("test"):
            result = self.aws_lambda.invoke(
                FunctionName=self.function_name,
                Payload=json.dumps({"message": "success"}),
            )

        assert result["StatusCode"] == 200
        result_payload = json.loads(result["Payload"].read().decode("utf-8"))
        assert "message" in result_payload
        assert result_payload["message"] == "success"

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "Invoke"
        endpoint = f"https://lambda.{self.lambda_region}.amazonaws.com"
        assert boto_span.data["boto3"]["ep"] == endpoint
        assert boto_span.data["boto3"]["reg"] == self.lambda_region
        assert "FunctionName" in boto_span.data["boto3"]["payload"]
        assert boto_span.data["boto3"]["payload"]["FunctionName"] == self.function_name
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert boto_span.data["http"]["url"] == f"{endpoint}:443/Invoke"

        assert "X-Capture-This-Too" in boto_span.data["http"]["header"]
        assert boto_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in boto_span.data["http"]["header"]
        assert boto_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

        agent.options.extra_http_headers = original_extra_http_headers
