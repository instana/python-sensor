# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from collections import defaultdict
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Dict, Generator

import pytest
import wrapt

from instana import get_aws_lambda_handler, lambda_handler
from instana.agent.aws_lambda import AWSLambdaAgent
from instana.collector.aws_lambda import AWSLambdaCollector
from instana.instrumentation.aws.lambda_inst import lambda_handler_with_instana
from instana.instrumentation.aws.triggers import read_http_query_params
from instana.options import AWSLambdaOptions
from instana.singletons import get_agent
from instana.util.aws import normalize_aws_lambda_arn
from instana.util.ids import hex_id

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan

# Mock Context object
class MockContext(dict):
    def __init__(self, **kwargs: Dict[str, Any]) -> None:
        super(MockContext, self).__init__(**kwargs)
        self.invoked_function_arn = (
            "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        self.function_name = "TestPython"
        self.function_version = "1"


# This is the target handler that will be instrumented for these tests
def my_lambda_handler(event: object, context: object) -> Dict[str, Any]:
    # print("target_handler called")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"site": "pwpush.com", "response": 204}),
    }


# We only want to monkey patch the test handler once so do it here
os.environ["LAMBDA_HANDLER"] = "tests_aws.01_lambda.test_lambda.my_lambda_handler"
module_name, function_name = get_aws_lambda_handler()
wrapt.wrap_function_wrapper(module_name, function_name, lambda_handler_with_instana)


def my_errored_lambda_handler(event: object, context: object) -> Dict[str, Any]:
    return {
        "statusCode": 500,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"site": "wikipedia.org", "response": 500}),
    }


os.environ["LAMBDA_HANDLER"] = (
    "tests_aws.01_lambda.test_lambda.my_errored_lambda_handler"
)
module_name, function_name = get_aws_lambda_handler()
wrapt.wrap_function_wrapper(module_name, function_name, lambda_handler_with_instana)


class TestLambda:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"
        os.environ["LAMBDA_HANDLER"] = (
            "tests_aws.01_lambda.test_lambda.my_lambda_handler"
        )
        self.pwd = os.path.dirname(os.path.realpath(__file__))
        self.context = MockContext()
        self.agent: AWSLambdaAgent = get_agent()
        yield
        # tearDown
        # Reset collector config 
        self.agent.collector.snapshot_data_sent = False
        # Reset all environment variables of consequence
        if "AWS_EXECUTION_ENV" in os.environ:
            os.environ.pop("AWS_EXECUTION_ENV")
        if "LAMBDA_HANDLER" in os.environ:
            os.environ.pop("LAMBDA_HANDLER")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_ENDPOINT_PROXY" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_PROXY")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")
        if "INSTANA_SERVICE_NAME" in os.environ:
            os.environ.pop("INSTANA_SERVICE_NAME")
        if "INSTANA_DEBUG" in os.environ:
            os.environ.pop("INSTANA_DEBUG")
        if "INSTANA_LOG_LEVEL" in os.environ:
            os.environ.pop("INSTANA_LOG_LEVEL")

    def test_invalid_options(self) -> None:
        # None of the required env vars are available...
        if "LAMBDA_HANDLER" in os.environ:
            os.environ.pop("LAMBDA_HANDLER")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

        self.agent = AWSLambdaAgent()
        assert not self.agent._can_send
        assert not self.agent.collector
        # Assign a collector to fix CI  tests
        self.agent.collector = AWSLambdaCollector(self.agent)

    def test_secrets(self) -> None:
        assert hasattr(self.agent.options, "secrets_matcher")
        assert self.agent.options.secrets_matcher == "contains-ignore-case"
        assert hasattr(self.agent.options, "secrets_list")
        assert self.agent.options.secrets_list == ["key", "pass", "secret"]

    def test_has_extra_http_headers(self) -> None:
        assert hasattr(self.agent, "options")
        assert hasattr(self.agent.options, "extra_http_headers")

    def test_has_options(self) -> None:
        assert hasattr(self.agent, "options")
        assert isinstance(self.agent.options, AWSLambdaOptions)
        assert self.agent.options.endpoint_proxy == {}

    def test_get_handler(self) -> None:
        os.environ["LAMBDA_HANDLER"] = "tests.lambda_handler"
        handler_module, handler_function = get_aws_lambda_handler()

        assert "tests" == handler_module
        assert "lambda_handler" == handler_function

    def test_get_handler_with_multi_subpackages(self) -> None:
        os.environ["LAMBDA_HANDLER"] = "tests.one.two.three.lambda_handler"
        handler_module, handler_function = get_aws_lambda_handler()

        assert "tests.one.two.three" == handler_module
        assert "lambda_handler" == handler_function

    def test_get_handler_with_space_in_it(self) -> None:
        os.environ["LAMBDA_HANDLER"] = " tests.another_module.lambda_handler"
        handler_module, handler_function = get_aws_lambda_handler()

        assert "tests.another_module" == handler_module
        assert "lambda_handler" == handler_function

        os.environ["LAMBDA_HANDLER"] = "tests.another_module.lambda_handler    "
        handler_module, handler_function = get_aws_lambda_handler()

        assert "tests.another_module" == handler_module
        assert "lambda_handler" == handler_function

    def test_agent_extra_http_headers(self) -> None:
        os.environ["INSTANA_EXTRA_HTTP_HEADERS"] = (
            "X-Test-Header;X-Another-Header;X-And-Another-Header"
        )
        self.agent = AWSLambdaAgent()

        assert self.agent.options.extra_http_headers
        should_headers = ["x-test-header", "x-another-header", "x-and-another-header"]
        assert should_headers == self.agent.options.extra_http_headers

    def test_custom_proxy(self) -> None:
        os.environ["INSTANA_ENDPOINT_PROXY"] = "http://myproxy.123"
        self.agent = AWSLambdaAgent()

        assert self.agent.options.endpoint_proxy == {"https": "http://myproxy.123"}

    def test_custom_service_name(self, trace_id: int, span_id: int) -> None:
        os.environ["INSTANA_SERVICE_NAME"] = "Legion"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"
        # We need reset the AWSLambdaOptions with new INSTANA_SERVICE_NAME
        self.agent.options = AWSLambdaOptions()
        
        with open(
            self.pwd + "/../data/lambda/api_gateway_event.json", "r"
        ) as json_file:
            event = json.load(json_file)

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)
        os.environ.pop("INSTANA_SERVICE_NAME")

        assert isinstance(result, dict)
        assert "headers" in result
        assert "Server-Timing" in result["headers"]

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()

        assert "metrics" in payload
        assert "spans" in payload
        assert len(payload.keys()) == 2

        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 1
        plugin_data = payload["metrics"]["plugins"][0]

        assert plugin_data["name"] == "com.instana.plugin.aws.lambda"
        assert (
            plugin_data["entityId"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        assert len(payload["spans"]) >= 1

        span = payload["spans"].pop()
        assert span.n == "aws.lambda.entry"
        assert span.t == hex_id(trace_id)
        assert span.s
        assert span.p == hex_id(span_id)
        assert span.ts

        server_timing_value = f"intid;desc={hex_id(trace_id)}"
        assert result["headers"]["Server-Timing"] == server_timing_value

        assert span.f == {
            "hl": True,
            "cp": "aws",
            "e": "arn:aws:lambda:us-east-2:12345:function:TestPython:1",
        }
        assert span.sy

        assert not span.ec
        assert not span.data["lambda"]["error"]

        assert (
            span.data["lambda"]["arn"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        assert not span.data["lambda"]["alias"]
        assert span.data["lambda"]["runtime"] == "python"
        assert span.data["lambda"]["functionName"] == "TestPython"
        assert span.data["lambda"]["functionVersion"] == "1"

        assert span.data["service"] == "Legion"

        assert span.data["lambda"]["trigger"] == "aws:api.gateway"
        assert span.data["http"]["method"] == "POST"
        assert span.data["http"]["status"] == 200
        assert span.data["http"]["url"] == "/path/to/resource"
        assert span.data["http"]["path_tpl"] == "/{proxy+}"
        assert span.data["http"]["params"] == "foo=['bar']"

    def test_api_gateway_trigger_tracing(self, trace_id: int, span_id: int) -> None:
        with open(
            self.pwd + "/../data/lambda/api_gateway_event.json", "r"
        ) as json_file:
            event = json.load(json_file)

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        assert isinstance(result, dict)
        assert "headers" in result
        assert "Server-Timing" in result["headers"]

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()

        assert "metrics" in payload
        assert "spans" in payload
        assert len(payload.keys()) == 2

        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 1
        plugin_data = payload["metrics"]["plugins"][0]

        assert plugin_data["name"] == "com.instana.plugin.aws.lambda"
        assert (
            plugin_data["entityId"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        assert len(payload["spans"]) >= 1

        span = payload["spans"].pop()
        assert span.n == "aws.lambda.entry"
        assert span.t == hex_id(trace_id)
        assert span.s
        assert span.p == hex_id(span_id)
        assert span.ts

        server_timing_value = f"intid;desc={hex_id(trace_id)}"
        assert result["headers"]["Server-Timing"] == server_timing_value

        assert span.f == {
            "hl": True,
            "cp": "aws",
            "e": "arn:aws:lambda:us-east-2:12345:function:TestPython:1",
        }
        assert span.sy

        assert not span.ec
        assert not span.data["lambda"]["error"]

        assert (
            span.data["lambda"]["arn"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        assert not span.data["lambda"]["alias"]
        assert span.data["lambda"]["runtime"] == "python"
        assert span.data["lambda"]["functionName"] == "TestPython"
        assert span.data["lambda"]["functionVersion"] == "1"
        assert not span.data["service"]

        assert span.data["lambda"]["trigger"] == "aws:api.gateway"
        assert span.data["http"]["method"] == "POST"
        assert span.data["http"]["status"] == 200
        assert span.data["http"]["url"] == "/path/to/resource"
        assert span.data["http"]["path_tpl"] == "/{proxy+}"
        assert span.data["http"]["params"] == "foo=['bar']"

    def test_api_gateway_v2_trigger_tracing(self) -> None:
        with open(
            self.pwd + "/../data/lambda/api_gateway_v2_event.json", "r"
        ) as json_file:
            event = json.load(json_file)

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)
        assert result["statusCode"] == 200

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()
        span = self.__validate_result_and_payload_for_gateway_v2_trace(result, payload)

        assert not span.ec
        assert not span.data["lambda"]["error"]
        assert span.data["http"]["status"] == 200

    def test_api_gateway_v2_trigger_errored_tracing(self) -> None:
        with open(
            self.pwd + "/../data/lambda/api_gateway_v2_event.json", "r"
        ) as json_file:
            event = json.load(json_file)

        os.environ["LAMBDA_HANDLER"] = (
            "tests_aws.01_lambda.test_lambda.my_errored_lambda_handler"
        )

        result = lambda_handler(event, self.context)
        assert result["statusCode"] == 500

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()
        span = self.__validate_result_and_payload_for_gateway_v2_trace(result, payload)

        assert span.ec == 1
        assert span.data["lambda"]["error"] == "HTTP status 500"
        assert span.data["http"]["status"] == 500

    def test_application_lb_trigger_tracing(self, trace_id: int, span_id: int) -> None:
        with open(
            self.pwd + "/../data/lambda/api_gateway_event.json", "r"
        ) as json_file:
            event = json.load(json_file)

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        assert isinstance(result, dict)
        assert "headers" in result
        assert "Server-Timing" in result["headers"]

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()

        assert "metrics" in payload
        assert "spans" in payload
        assert len(payload.keys()) == 2

        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 1
        plugin_data = payload["metrics"]["plugins"][0]

        assert plugin_data["name"] == "com.instana.plugin.aws.lambda"
        assert (
            plugin_data["entityId"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        assert len(payload["spans"]) >= 1

        span = payload["spans"].pop()
        assert span.n == "aws.lambda.entry"
        assert span.t == hex_id(trace_id)
        assert span.s
        assert span.p == hex_id(span_id)
        assert span.ts

        server_timing_value = f"intid;desc={hex_id(trace_id)}"
        assert result["headers"]["Server-Timing"] == server_timing_value

        assert span.f == {
            "hl": True,
            "cp": "aws",
            "e": "arn:aws:lambda:us-east-2:12345:function:TestPython:1",
        }
        assert span.sy

        assert not span.ec
        assert not span.data["lambda"]["error"]

        assert (
            span.data["lambda"]["arn"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        assert not span.data["lambda"]["alias"]
        assert span.data["lambda"]["runtime"] == "python"
        assert span.data["lambda"]["functionName"] == "TestPython"
        assert span.data["lambda"]["functionVersion"] == "1"
        assert not span.data["service"]

        assert span.data["lambda"]["trigger"] == "aws:api.gateway"
        assert span.data["http"]["method"] == "POST"
        assert span.data["http"]["status"] == 200
        assert span.data["http"]["url"] == "/path/to/resource"
        assert span.data["http"]["params"] == "foo=['bar']"

    def test_cloudwatch_trigger_tracing(self, trace_id: int) -> None:
        with open(self.pwd + "/../data/lambda/cloudwatch_event.json", "r") as json_file:
            event = json.load(json_file)

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        assert isinstance(result, dict)
        assert "headers" in result
        assert "Server-Timing" in result["headers"]

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()

        assert "metrics" in payload
        assert "spans" in payload
        assert len(payload.keys()) == 2

        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 1
        plugin_data = payload["metrics"]["plugins"][0]

        assert plugin_data["name"] == "com.instana.plugin.aws.lambda"
        assert (
            plugin_data["entityId"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        assert len(payload["spans"]) >= 1

        span = payload["spans"].pop()
        assert span.n == "aws.lambda.entry"
        assert span.t
        assert span.s
        assert not span.p
        assert span.ts

        server_timing_value = f"intid;desc={hex_id(int(span.t, 16))}"
        assert result["headers"]["Server-Timing"] == server_timing_value

        assert span.f == {
            "hl": True,
            "cp": "aws",
            "e": "arn:aws:lambda:us-east-2:12345:function:TestPython:1",
        }
        assert not span.sy
        assert not span.ec
        assert not span.data["lambda"]["error"]

        assert (
            span.data["lambda"]["arn"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        assert not span.data["lambda"]["alias"]
        assert span.data["lambda"]["runtime"] == "python"
        assert span.data["lambda"]["functionName"] == "TestPython"
        assert span.data["lambda"]["functionVersion"] == "1"
        assert not span.data["service"]

        assert span.data["lambda"]["trigger"] == "aws:cloudwatch.events"
        assert (
            span.data["lambda"]["cw"]["events"]["id"]
            == "cdc73f9d-aea9-11e3-9d5a-835b769c0d9c"
        )
        assert not span.data["lambda"]["cw"]["events"]["more"]
        assert isinstance(span.data["lambda"]["cw"]["events"]["resources"], list)

        assert len(span.data["lambda"]["cw"]["events"]["resources"]) == 1
        assert (
            span.data["lambda"]["cw"]["events"]["resources"][0]
            == "arn:aws:events:eu-west-1:123456789012:rule/ExampleRule"
        )

    def test_cloudwatch_logs_trigger_tracing(self) -> None:
        with open(
            self.pwd + "/../data/lambda/cloudwatch_logs_event.json", "r"
        ) as json_file:
            event = json.load(json_file)

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        assert isinstance(result, dict)
        assert "headers" in result
        assert "Server-Timing" in result["headers"]

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()

        assert "metrics" in payload
        assert "spans" in payload
        assert len(payload.keys()) == 2

        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 1
        plugin_data = payload["metrics"]["plugins"][0]

        assert plugin_data["name"] == "com.instana.plugin.aws.lambda"
        assert (
            plugin_data["entityId"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        assert len(payload["spans"]) >= 1

        span = payload["spans"].pop()
        assert span.n == "aws.lambda.entry"
        assert span.t
        assert span.s
        assert not span.p
        assert span.ts

        server_timing_value = f"intid;desc={hex_id(int(span.t, 16))}"
        assert result["headers"]["Server-Timing"] == server_timing_value

        assert span.f == {
            "hl": True,
            "cp": "aws",
            "e": "arn:aws:lambda:us-east-2:12345:function:TestPython:1",
        }
        assert not span.sy

        assert not span.ec
        assert not span.data["lambda"]["error"]

        assert (
            span.data["lambda"]["arn"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        assert not span.data["lambda"]["alias"]
        assert span.data["lambda"]["runtime"] == "python"
        assert span.data["lambda"]["functionName"] == "TestPython"
        assert span.data["lambda"]["functionVersion"] == "1"
        assert not span.data["service"]

        assert span.data["lambda"]["trigger"] == "aws:cloudwatch.logs"
        assert "decodingError" not in span.data["lambda"]["cw"]["logs"]
        assert span.data["lambda"]["cw"]["logs"]["group"] == "testLogGroup"
        assert span.data["lambda"]["cw"]["logs"]["stream"] == "testLogStream"
        assert not span.data["lambda"]["cw"]["logs"]["more"]
        assert isinstance(span.data["lambda"]["cw"]["logs"]["events"], list)
        assert len(span.data["lambda"]["cw"]["logs"]["events"]) == 2
        assert (
            span.data["lambda"]["cw"]["logs"]["events"][0]
            == "[ERROR] First test message"
        )
        assert (
            span.data["lambda"]["cw"]["logs"]["events"][1]
            == "[ERROR] Second test message"
        )

    def test_s3_trigger_tracing(self) -> None:
        with open(self.pwd + "/../data/lambda/s3_event.json", "r") as json_file:
            event = json.load(json_file)

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        assert isinstance(result, dict)
        assert "headers" in result
        assert "Server-Timing" in result["headers"]

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()

        assert "metrics" in payload
        assert "spans" in payload
        assert len(payload.keys()) == 2

        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 1
        plugin_data = payload["metrics"]["plugins"][0]

        assert plugin_data["name"] == "com.instana.plugin.aws.lambda"
        assert (
            plugin_data["entityId"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        assert len(payload["spans"]) >= 1

        span = payload["spans"].pop()
        assert span.n == "aws.lambda.entry"
        assert span.t
        assert span.s
        assert not span.p
        assert span.ts

        server_timing_value = f"intid;desc={hex_id(int(span.t, 16))}"
        assert result["headers"]["Server-Timing"] == server_timing_value

        assert span.f == {
            "hl": True,
            "cp": "aws",
            "e": "arn:aws:lambda:us-east-2:12345:function:TestPython:1",
        }
        assert not span.sy

        assert not span.ec
        assert not span.data["lambda"]["error"]

        assert (
            span.data["lambda"]["arn"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        assert not span.data["lambda"]["alias"]
        assert span.data["lambda"]["runtime"] == "python"
        assert span.data["lambda"]["functionName"] == "TestPython"
        assert span.data["lambda"]["functionVersion"] == "1"
        assert not span.data["service"]

        assert span.data["lambda"]["trigger"] == "aws:s3"
        assert isinstance(span.data["lambda"]["s3"]["events"], list)
        events = span.data["lambda"]["s3"]["events"]
        assert len(events) == 1
        event = events[0]
        assert event["event"] == "ObjectCreated:Put"
        assert event["bucket"] == "example-bucket"
        assert event["object"] == "test/key"

    def test_sqs_trigger_tracing(self) -> None:
        with open(self.pwd + "/../data/lambda/sqs_event.json", "r") as json_file:
            event = json.load(json_file)

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        assert isinstance(result, dict)
        assert "headers" in result
        assert "Server-Timing" in result["headers"]

        time.sleep(1)
        payload = self.agent.collector.prepare_payload()

        assert "metrics" in payload
        assert "spans" in payload
        assert len(payload.keys()) == 2

        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 1
        plugin_data = payload["metrics"]["plugins"][0]

        assert plugin_data["name"] == "com.instana.plugin.aws.lambda"
        assert (
            plugin_data["entityId"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        assert len(payload["spans"]) >= 1

        span = payload["spans"].pop()
        assert span.n == "aws.lambda.entry"
        assert span.t
        assert span.s
        assert not span.p
        assert span.ts

        server_timing_value = f"intid;desc={hex_id(int(span.t, 16))}"
        assert result["headers"]["Server-Timing"] == server_timing_value

        assert span.f == {
            "hl": True,
            "cp": "aws",
            "e": "arn:aws:lambda:us-east-2:12345:function:TestPython:1",
        }
        assert not span.sy

        assert not span.ec
        assert not span.data["lambda"]["error"]

        assert (
            span.data["lambda"]["arn"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        assert not span.data["lambda"]["alias"]
        assert span.data["lambda"]["runtime"] == "python"
        assert span.data["lambda"]["functionName"] == "TestPython"
        assert span.data["lambda"]["functionVersion"] == "1"
        assert not span.data["service"]

        assert span.data["lambda"]["trigger"] == "aws:sqs"
        assert isinstance(span.data["lambda"]["sqs"]["messages"], list)
        messages = span.data["lambda"]["sqs"]["messages"]
        assert len(messages) == 1
        message = messages[0]
        assert message["queue"] == "arn:aws:sqs:us-west-1:123456789012:MyQueue"

    def test_read_query_params(self) -> None:
        event = {
            "queryStringParameters": {"foo": "bar"},
            "multiValueQueryStringParameters": {"foo": ["bar"]},
        }
        params = read_http_query_params(event)
        assert params == "foo=['bar']"

    def test_read_query_params_with_none_data(self) -> None:
        event = {"queryStringParameters": None, "multiValueQueryStringParameters": None}
        params = read_http_query_params(event)
        assert params == ""

    def test_read_query_params_with_bad_event(self) -> None:
        event = None
        params = read_http_query_params(event)
        assert params == ""

    def test_arn_parsing(self) -> None:
        ctx = MockContext()

        assert (
            normalize_aws_lambda_arn(ctx)
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        # Without version should return a fully qualified ARN (with version)
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-2:12345:function:TestPython"
        assert (
            normalize_aws_lambda_arn(ctx)
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        # Fully qualified already with the '$LATEST' special tag
        ctx.invoked_function_arn = (
            "arn:aws:lambda:us-east-2:12345:function:TestPython:$LATEST"
        )
        assert (
            normalize_aws_lambda_arn(ctx)
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:$LATEST"
        )

    def test_agent_default_log_level(self) -> None:
        assert self.agent.options.log_level == logging.WARNING

    def __validate_result_and_payload_for_gateway_v2_trace(self, result: Dict[str, Any], payload: defaultdict) -> "InstanaSpan":
        assert isinstance(result, dict)
        assert "headers" in result
        assert "Server-Timing" in result["headers"]
        assert "statusCode" in result

        assert "metrics" in payload
        assert "spans" in payload
        assert len(payload.keys()) == 2

        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 1
        plugin_data = payload["metrics"]["plugins"][0]

        assert plugin_data["name"] == "com.instana.plugin.aws.lambda"
        assert (
            plugin_data["entityId"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )

        assert len(payload["spans"]) >= 1

        span = payload["spans"].pop()
        assert span.n == "aws.lambda.entry"
        trace_id = "0000000000001234"
        assert span.t == trace_id
        assert span.s
        assert span.p == "0000000000004567"
        assert span.ts

        server_timing_value = f"intid;desc={trace_id}"
        assert result["headers"]["Server-Timing"] == server_timing_value

        assert span.f == {
            "hl": True,
            "cp": "aws",
            "e": "arn:aws:lambda:us-east-2:12345:function:TestPython:1",
        }
        assert span.sy

        assert (
            span.data["lambda"]["arn"]
            == "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        )
        assert not span.data["lambda"]["alias"]
        assert span.data["lambda"]["runtime"] == "python"
        assert span.data["lambda"]["functionName"] == "TestPython"
        assert span.data["lambda"]["functionVersion"] == "1"
        assert not span.data["service"]

        assert span.data["lambda"]["trigger"] == "aws:api.gateway"
        assert span.data["http"]["method"] == "POST"
        assert span.data["http"]["url"] == "/my/path"
        assert span.data["http"]["path_tpl"] == "/my/{resource}"
        assert span.data["http"]["params"] == "secret=key&q=term"

        return span