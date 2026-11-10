# (c) Copyright IBM Corp. 2026

import base64
import gzip
import json
from collections.abc import Callable, Generator
from typing import Any, Optional, Union
from unittest.mock import MagicMock

import pytest

from instana.instrumentation.aws.triggers import (
    capture_extra_headers,
    enrich_lambda_span,
    get_context,
    is_api_gateway_proxy_trigger,
    is_api_gateway_v2_proxy_trigger,
    is_application_load_balancer_trigger,
    is_cloudwatch_logs_trigger,
    is_cloudwatch_trigger,
    is_s3_trigger,
    is_sqs_trigger,
    read_http_query_params,
)
from instana.propagators.format import Format

API_GATEWAY_EVENT = {
    "resource": "/{proxy+}",
    "path": "/path/to/resource",
    "httpMethod": "POST",
    "headers": {"X-Custom": "custom-value"},
    "queryStringParameters": {"foo": "bar"},
}

API_GATEWAY_V2_EVENT = {
    "version": "2.0",
    "routeKey": "GET /items/{id}",
    "requestContext": {
        "apiId": "api",
        "stage": "$default",
        "http": {"method": "GET", "path": "/items/42"},
    },
    "headers": {"X-Custom": "custom-value"},
    "queryStringParameters": {"a": "b"},
}

ALB_EVENT = {
    "requestContext": {"elb": {"targetGroupArn": "arn"}},
    "httpMethod": "GET",
    "path": "/alb",
    "headers": {"X-Custom": "custom-value"},
    "queryStringParameters": {"x": "y"},
}

CLOUDWATCH_EVENT = {
    "id": "event-id",
    "source": "aws.events",
    "detail-type": "Scheduled Event",
    "resources": ["arn:1", "arn:2"],
}

S3_EVENT = {
    "Records": [
        {
            "eventSource": "aws:s3",
            "eventName": "ObjectCreated:Put",
            "s3": {"bucket": {"name": "my-bucket"}, "object": {"key": "my-key"}},
        }
    ]
}

SQS_EVENT = {
    "Records": [{"eventSource": "aws:sqs", "eventSourceARN": "arn:aws:sqs:queue"}]
}


def make_logs_event(log_data: dict[str, Any]) -> dict[str, Any]:
    compressed = gzip.compress(json.dumps(log_data).encode("utf-8"))
    return {"awslogs": {"data": base64.b64encode(compressed).decode("utf-8")}}


def get_attributes(span: MagicMock) -> dict[str, Any]:
    return {call.args[0]: call.args[1] for call in span.set_attribute.call_args_list}


class TestTriggerDetection:
    def test_is_api_gateway_proxy_trigger(self) -> None:
        assert is_api_gateway_proxy_trigger(API_GATEWAY_EVENT)
        assert not is_api_gateway_proxy_trigger({"resource": "/", "path": "/"})

    @pytest.mark.parametrize(
        "event, expected",
        [
            (API_GATEWAY_V2_EVENT, True),
            ({"requestContext": {}}, False),
            ({"version": "1.0", "requestContext": {}}, False),
            ({"version": "2.0", "requestContext": {"apiId": "a"}}, False),
        ],
    )
    def test_is_api_gateway_v2_proxy_trigger(
        self, event: dict[str, Any], expected: bool
    ) -> None:
        assert is_api_gateway_v2_proxy_trigger(event) == expected

    def test_is_application_load_balancer_trigger(self) -> None:
        assert is_application_load_balancer_trigger(ALB_EVENT)
        assert not is_application_load_balancer_trigger({"requestContext": {}})
        assert not is_application_load_balancer_trigger({})

    @pytest.mark.parametrize(
        "event, expected",
        [
            (CLOUDWATCH_EVENT, True),
            ({"source": "aws.events"}, False),
            ({"source": "other", "detail-type": "Scheduled Event"}, False),
            ({"source": "aws.events", "detail-type": "Other"}, False),
        ],
    )
    def test_is_cloudwatch_trigger(self, event: dict[str, Any], expected: bool) -> None:
        assert is_cloudwatch_trigger(event) == expected

    def test_is_cloudwatch_logs_trigger(self) -> None:
        assert is_cloudwatch_logs_trigger({"awslogs": {"data": "x"}})
        assert not is_cloudwatch_logs_trigger({})
        assert not is_cloudwatch_logs_trigger("not-a-dict")

    @pytest.mark.parametrize(
        "checker, event, expected",
        [
            (is_s3_trigger, S3_EVENT, True),
            (is_s3_trigger, SQS_EVENT, False),
            (is_s3_trigger, {"Records": []}, False),
            (is_s3_trigger, {}, False),
            (is_sqs_trigger, SQS_EVENT, True),
            (is_sqs_trigger, S3_EVENT, False),
            (is_sqs_trigger, {"Records": []}, False),
            (is_sqs_trigger, {}, False),
        ],
    )
    def test_is_records_trigger(
        self,
        checker: Callable[[dict[str, Any]], bool],
        event: dict[str, Any],
        expected: bool,
    ) -> None:
        assert checker(event) == expected


class TestGetContext:
    @pytest.mark.parametrize(
        "event, expected_carrier",
        [
            (API_GATEWAY_EVENT, API_GATEWAY_EVENT["headers"]),
            (API_GATEWAY_V2_EVENT, API_GATEWAY_V2_EVENT["headers"]),
            (ALB_EVENT, ALB_EVENT["headers"]),
        ],
    )
    def test_get_context_proxy_event_uses_headers(
        self, event: dict[str, Any], expected_carrier: dict[str, Any]
    ) -> None:
        tracer = MagicMock()
        result = get_context(tracer, event)
        assert result == tracer.extract.return_value
        tracer.extract.assert_called_once_with(
            Format.HTTP_HEADERS, expected_carrier, disable_w3c_trace_context=True
        )

    def test_get_context_non_proxy_event_uses_event(self) -> None:
        tracer = MagicMock()
        event = {"custom": "event"}
        result = get_context(tracer, event)
        assert result == tracer.extract.return_value
        tracer.extract.assert_called_once_with(
            Format.HTTP_HEADERS, event, disable_w3c_trace_context=True
        )


class TestReadHttpQueryParams:
    @pytest.mark.parametrize(
        "event, expected",
        [
            (None, ""),
            ("string", ""),
            ({}, ""),
            ({"queryStringParameters": {"a": "b", "c": "d"}}, "a=b&c=d"),
            ({"multiValueQueryStringParameters": {"a": ["1", "2"]}}, "a=['1', '2']"),
            (
                {
                    "multiValueQueryStringParameters": {"m": "1"},
                    "queryStringParameters": {"q": "2"},
                },
                "m=1",
            ),
        ],
    )
    def test_read_http_query_params(
        self, event: Optional[Union[dict[str, Any], str]], expected: str
    ) -> None:
        assert read_http_query_params(event) == expected

    def test_read_http_query_params_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")

        class BadValue:
            def __str__(self) -> str:
                raise RuntimeError("boom")

        event = {"queryStringParameters": {"a": BadValue()}}
        assert read_http_query_params(event) == ""
        assert "read_http_query_params error" in caplog.text


class TestCaptureExtraHeaders:
    def test_capture_extra_headers_case_insensitive(self) -> None:
        span = MagicMock()
        event = {"headers": {"x-custom": "value", "Other": "ignored"}}
        capture_extra_headers(event, span, ["X-Custom"])
        span.set_attribute.assert_called_once_with("http.header.X-Custom", "value")

    def test_capture_extra_headers_no_headers(self) -> None:
        span = MagicMock()
        capture_extra_headers({}, span, ["X-Custom"])
        span.set_attribute.assert_not_called()

    def test_capture_extra_headers_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        span = MagicMock()
        capture_extra_headers(None, span, ["X-Custom"])
        span.set_attribute.assert_not_called()
        assert "capture_extra_headers error" in caplog.text


class TestEnrichLambdaSpan:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.agent = MagicMock()
        self.agent.collector.get_fq_arn.return_value = "arn:aws:lambda:fn"
        self.agent.options.extra_http_headers = ["X-Custom"]
        self.span = MagicMock()
        self.context = MagicMock()
        self.context.function_name = "my-function"
        self.context.function_version = "$LATEST"
        yield
        self.span = None

    def enrich(
        self, event: Optional[Union[dict[str, Any], str, list[str]]]
    ) -> dict[str, Any]:
        enrich_lambda_span(self.agent, self.span, event, self.context)
        return get_attributes(self.span)

    def test_enrich_lambda_span_unknown_trigger_sets_base_attributes(self) -> None:
        attributes = self.enrich({"unknown": "event"})
        assert attributes["lambda.arn"] == "arn:aws:lambda:fn"
        assert attributes["lambda.name"] == "my-function"
        assert attributes["lambda.version"] == "$LATEST"
        assert attributes["lambda.trigger"] == "unknown"

    @pytest.mark.parametrize("event", [None, {}, "string", ["list"]])
    def test_enrich_lambda_span_bad_event(
        self, event: Optional[Union[dict[str, Any], str, list[str]]]
    ) -> None:
        attributes = self.enrich(event)
        assert "lambda.trigger" not in attributes
        assert attributes["lambda.name"] == "my-function"

    def test_enrich_lambda_span_api_gateway(self) -> None:
        attributes = self.enrich(API_GATEWAY_EVENT)
        assert attributes["lambda.trigger"] == "aws:api.gateway"
        assert attributes["http.method"] == "POST"
        assert attributes["http.url"] == "/path/to/resource"
        assert attributes["http.path_tpl"] == "/{proxy+}"
        assert attributes["http.params"] == "foo=bar"
        assert attributes["http.header.X-Custom"] == "custom-value"

    def test_enrich_lambda_span_api_gateway_no_extra_headers(self) -> None:
        self.agent.options.extra_http_headers = None
        attributes = self.enrich(API_GATEWAY_EVENT)
        assert "http.header.X-Custom" not in attributes

    def test_enrich_lambda_span_api_gateway_v2(self) -> None:
        attributes = self.enrich(API_GATEWAY_V2_EVENT)
        assert attributes["lambda.trigger"] == "aws:api.gateway"
        assert attributes["http.method"] == "GET"
        assert attributes["http.url"] == "/items/42"
        assert attributes["http.path_tpl"] == "/items/{id}"
        assert attributes["http.params"] == "a=b"
        assert attributes["http.header.X-Custom"] == "custom-value"

    def test_enrich_lambda_span_api_gateway_v2_no_extra_headers(self) -> None:
        self.agent.options.extra_http_headers = None
        attributes = self.enrich(API_GATEWAY_V2_EVENT)
        assert "http.header.X-Custom" not in attributes

    def test_enrich_lambda_span_application_load_balancer(self) -> None:
        attributes = self.enrich(ALB_EVENT)
        assert attributes["lambda.trigger"] == "aws:application.load.balancer"
        assert attributes["http.method"] == "GET"
        assert attributes["http.url"] == "/alb"
        assert attributes["http.params"] == "x=y"
        assert attributes["http.header.X-Custom"] == "custom-value"

    def test_enrich_lambda_span_application_load_balancer_no_extra_headers(
        self,
    ) -> None:
        self.agent.options.extra_http_headers = None
        attributes = self.enrich(ALB_EVENT)
        assert "http.header.X-Custom" not in attributes

    def test_enrich_lambda_span_cloudwatch_events(self) -> None:
        attributes = self.enrich(CLOUDWATCH_EVENT)
        assert attributes["lambda.trigger"] == "aws:cloudwatch.events"
        assert attributes["data.lambda.cw.events.id"] == "event-id"
        assert attributes["lambda.cw.events.more"] is False
        assert attributes["lambda.cw.events.resources"] == ["arn:1", "arn:2"]

    def test_enrich_lambda_span_cloudwatch_events_truncation(self) -> None:
        event = dict(CLOUDWATCH_EVENT)
        event["resources"] = ["a" * 250, "b", "c", "d"]
        attributes = self.enrich(event)
        assert attributes["lambda.cw.events.more"] is True
        assert attributes["lambda.cw.events.resources"] == ["a" * 200, "b", "c"]

    def test_enrich_lambda_span_cloudwatch_logs(self) -> None:
        log_data = {
            "logGroup": "group",
            "logStream": "stream",
            "logEvents": [{"message": "m1"}, {"message": "x" * 250}],
        }
        attributes = self.enrich(make_logs_event(log_data))
        assert attributes["lambda.trigger"] == "aws:cloudwatch.logs"
        assert attributes["lambda.cw.logs.group"] == "group"
        assert attributes["lambda.cw.logs.stream"] == "stream"
        assert "lambda.cw.logs.more" not in attributes
        assert attributes["lambda.cw.logs.events"] == ["m1", "x" * 200]

    def test_enrich_lambda_span_cloudwatch_logs_more_than_three_events(self) -> None:
        log_data = {
            "logGroup": "group",
            "logStream": "stream",
            "logEvents": [{"message": f"m{i}"} for i in range(5)],
        }
        attributes = self.enrich(make_logs_event(log_data))
        assert attributes["lambda.cw.logs.more"] is True
        assert attributes["lambda.cw.logs.events"] == ["m0", "m1", "m2"]

    def test_enrich_lambda_span_cloudwatch_logs_without_data(self) -> None:
        attributes = self.enrich({"awslogs": {}})
        assert attributes["lambda.trigger"] == "aws:cloudwatch.logs"
        assert "lambda.cw.logs.events" not in attributes

    def test_enrich_lambda_span_cloudwatch_logs_decoding_error(self) -> None:
        attributes = self.enrich({"awslogs": {"data": "not-base64-gzip"}})
        assert attributes["lambda.trigger"] == "aws:cloudwatch.logs"
        assert "lambda.cw.logs.decodingError" in attributes

    def test_enrich_lambda_span_s3(self) -> None:
        attributes = self.enrich(S3_EVENT)
        assert attributes["lambda.trigger"] == "aws:s3"
        assert attributes["lambda.s3.events"] == [
            {
                "event": "ObjectCreated:Put",
                "bucket": "my-bucket",
                "object": "my-key",
            }
        ]

    def test_enrich_lambda_span_s3_missing_details_and_long_key(self) -> None:
        event = {
            "Records": [
                {"eventSource": "aws:s3", "eventName": "Created"},
                {
                    "eventSource": "aws:s3",
                    "eventName": "Removed",
                    "s3": {"bucket": {"name": "b"}, "object": {"key": "k" * 250}},
                },
                {
                    "eventSource": "aws:s3",
                    "eventName": "Other",
                    "s3": {"bucket": {"name": "b"}, "object": {}},
                },
            ]
        }
        attributes = self.enrich(event)
        assert attributes["lambda.s3.events"] == [
            {"event": "Created", "bucket": "Unknown", "object": ""},
            {"event": "Removed", "bucket": "b", "object": "k" * 200},
            {"event": "Other", "bucket": "b", "object": "Unknown"},
        ]

    def test_enrich_lambda_span_sqs(self) -> None:
        attributes = self.enrich(SQS_EVENT)
        assert attributes["lambda.trigger"] == "aws:sqs"
        assert attributes["lambda.sqs.messages"] == [{"queue": "arn:aws:sqs:queue"}]

    def test_enrich_lambda_span_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.agent.collector.get_fq_arn.side_effect = RuntimeError("boom")
        enrich_lambda_span(self.agent, self.span, {}, self.context)
        self.span.set_attribute.assert_not_called()
        assert "enrich_lambda_span error" in caplog.text
