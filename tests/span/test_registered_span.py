# (c) Copyright IBM Corp. 2024

import logging
import time
from typing import Any, Dict, Generator, Tuple

import pytest
from opentelemetry.trace import SpanKind

from instana.recorder import StanRecorder
from instana.span.registered_span import RegisteredSpan
from instana.span.span import InstanaSpan
from instana.span_context import SpanContext


class TestRegisteredSpan:
    @pytest.fixture(autouse=True)
    def _resource(
        self,
    ) -> Generator[None, None, None]:
        self.span = None
        yield

    @pytest.mark.parametrize(
        "span_name, expected_result, attributes",
        [
            ("wsgi", ("wsgi", SpanKind.SERVER, "http"), {}),
            ("rabbitmq", ("rabbitmq", SpanKind.SERVER, "rabbitmq"), {}),
            ("gcps-producer", ("gcps", SpanKind.CLIENT, "gcps"), {}),
            ("urllib3", ("urllib3", SpanKind.CLIENT, "http"), {}),
            (
                "rabbitmq",
                ("rabbitmq", SpanKind.CLIENT, "rabbitmq"),
                {"sort": "publish"},
            ),
            (
                "render",
                ("render", SpanKind.INTERNAL, "render"),
                {"arguments": "--quiet"},
            ),
        ],
    )
    def test_registered_span(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        span_name: str,
        expected_result: Tuple[str, int, str],
        attributes: Dict[str, Any],
    ) -> None:
        service_name = "test-registered-service"
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )
        reg_span = RegisteredSpan(self.span, None, service_name)

        assert expected_result[0] == reg_span.n
        assert expected_result[1] == reg_span.k
        assert service_name == reg_span.data["service"]
        assert expected_result[2] in reg_span.data.keys()

    def test_collect_http_attributes_with_attributes(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-registered-span"
        attributes = {
            "http.host": "localhost",
            "http.url": "https://www.instana.com",
            "http.header.test": "one more test",
        }
        service_name = "test-registered-service"
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )
        reg_span = RegisteredSpan(self.span, None, service_name)

        excepted_result = {
            "http.host": attributes["http.host"],
            "http.url": attributes["http.url"],
            "http.header.test": attributes["http.header.test"],
        }

        reg_span._collect_http_attributes(self.span)

        assert excepted_result["http.host"] == reg_span.data["http"]["host"]
        assert excepted_result["http.url"] == reg_span.data["http"]["url"]
        assert (
            excepted_result["http.header.test"]
            == reg_span.data["http"]["header"]["test"]
        )

    def test_populate_local_span_data_with_other_name(
        self,
        span_context: SpanContext,
        span_processor,
        caplog,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        span_name = "test-registered-span"
        service_name = "test-registered-service"
        self.span = InstanaSpan(span_name, span_context, span_processor)
        reg_span = RegisteredSpan(self.span, None, service_name)

        expected_msg = f"SpanRecorder: Unknown local span: {span_name}"

        reg_span._populate_local_span_data(self.span)

        assert expected_msg in caplog.messages

    @pytest.mark.parametrize(
        "span_name, service_name, attributes",
        [
            (
                "aws.lambda.entry",
                "lambda",
                {
                    "lambda.arn": "test",
                    "lambda.trigger": None,
                },
            ),
            (
                "celery-worker",
                "celery",
                {
                    "host": "localhost",
                    "port": 1234,
                },
            ),
            (
                "gcps-consumer",
                "gcps",
                {
                    "gcps.op": "consume",
                    "gcps.projid": "MY_PROJECT",
                    "gcps.sub": "MY_SUBSCRIPTION_NAME",
                },
            ),
            (
                "rpc-server",
                "rpc",
                {
                    "rpc.flavor": "Vanilla",
                    "rpc.host": "localhost",
                    "rpc.port": 1234,
                },
            ),
            (
                "kafka-consumer",
                "kafka",
                {
                    "kafka.service": "my-topic",
                    "kafka.access": "consume",
                },
            ),
        ],
    )
    def test_populate_entry_span_data(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        span_name: str,
        service_name: str,
        attributes: Dict[str, Any],
    ) -> None:
        self.span = InstanaSpan(span_name, span_context, span_processor)
        reg_span = RegisteredSpan(self.span, None, service_name)

        expected_result = {}
        for attr, value in attributes.items():
            attrl = attr.split(".")
            attrl = attrl[1] if len(attrl) > 1 else attrl[0]
            expected_result[attrl] = value

        self.span.set_attributes(attributes)
        reg_span._populate_entry_span_data(self.span)

        for attr, value in expected_result.items():
            assert value == reg_span.data[service_name][attr]

    @pytest.mark.parametrize(
        "attributes",
        [
            {
                "lambda.arn": "test",
                "lambda.trigger": "aws:api.gateway",
                "http.host": "localhost",
                "http.url": "https://www.instana.com",
            },
            {
                "lambda.arn": "test",
                "lambda.trigger": "aws:cloudwatch.events",
                "lambda.cw.events.resources": "Resource 1",
            },
            {
                "lambda.arn": "test",
                "lambda.trigger": "aws:cloudwatch.logs",
                "lambda.cw.logs.group": "My Group",
            },
            {
                "lambda.arn": "test",
                "lambda.trigger": "aws:s3",
                "lambda.s3.events": "Event 1",
            },
            {
                "lambda.arn": "test",
                "lambda.trigger": "aws:sqs",
                "lambda.sqs.messages": "Message 1",
            },
        ],
    )
    def test_populate_entry_span_data_AWSlambda(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        attributes: Dict[str, Any],
    ) -> None:
        span_name = "aws.lambda.entry"
        service_name = "lambda"
        expected_result = attributes.copy()

        self.span = InstanaSpan(span_name, span_context, span_processor)
        reg_span = RegisteredSpan(self.span, None, service_name)

        self.span.set_attributes(attributes)
        reg_span._populate_entry_span_data(self.span)

        assert "python" == reg_span.data["lambda"]["runtime"]
        assert "Unknown" == reg_span.data["lambda"]["functionName"]
        assert "test" == reg_span.data["lambda"]["arn"]
        assert expected_result["lambda.trigger"] == reg_span.data["lambda"]["trigger"]

        if expected_result["lambda.trigger"] == "aws:api.gateway":
            assert expected_result["http.host"] == reg_span.data["http"]["host"]
            assert expected_result["http.url"] == reg_span.data["http"]["url"]

        elif expected_result["lambda.trigger"] == "aws:cloudwatch.events":
            assert (
                expected_result["lambda.cw.events.resources"]
                == reg_span.data["lambda"]["cw"]["events"]["resources"]
            )
        elif expected_result["lambda.trigger"] == "aws:cloudwatch.logs":
            assert (
                expected_result["lambda.cw.logs.group"]
                == reg_span.data["lambda"]["cw"]["logs"]["group"]
            )
        elif expected_result["lambda.trigger"] == "aws:s3":
            assert (
                expected_result["lambda.s3.events"]
                == reg_span.data["lambda"]["s3"]["events"]
            )
        elif expected_result["lambda.trigger"] == "aws:sqs":
            assert (
                expected_result["lambda.sqs.messages"]
                == reg_span.data["lambda"]["sqs"]["messages"]
            )

    @pytest.mark.parametrize(
        "span_name, service_name, attributes",
        [
            (
                "cassandra",
                "cassandra",
                {
                    "cassandra.cluster": "my_cluster",
                    "cassandra.error": "minor error",
                },
            ),
            (
                "celery-client",
                "celery",
                {
                    "host": "localhost",
                    "port": 1234,
                },
            ),
            (
                "couchbase",
                "couchbase",
                {
                    "couchbase.hostname": "localhost",
                    "couchbase.error_type": 1234,
                },
            ),
            (
                "rabbitmq",
                "rabbitmq",
                {
                    "address": "localhost",
                    "key": 1234,
                },
            ),
            (
                "redis",
                "redis",
                {
                    "command": "ls -l",
                    "redis.error": "minor error",
                },
            ),
            (
                "rpc-client",
                "rpc",
                {
                    "rpc.flavor": "Vanilla",
                    "rpc.host": "localhost",
                    "rpc.port": 1234,
                },
            ),
            (
                "sqlalchemy",
                "sqlalchemy",
                {
                    "sqlalchemy.sql": "SELECT * FROM everything;",
                    "sqlalchemy.err": "Impossible select everything from everything!",
                },
            ),
            (
                "mysql",
                "mysql",
                {
                    "host": "localhost",
                    "port": 1234,
                },
            ),
            (
                "postgres",
                "pg",
                {
                    "host": "localhost",
                    "port": 1234,
                },
            ),
            (
                "mongo",
                "mongo",
                {
                    "command": "IDK",
                    "error": "minor error",
                },
            ),
            (
                "gcs",
                "gcs",
                {
                    "gcs.op": "produce",
                    "gcs.projectId": "MY_PROJECT",
                    "gcs.accessId": "Can not tell you!",
                },
            ),
            (
                "gcps-producer",
                "gcps",
                {
                    "gcps.op": "produce",
                    "gcps.projid": "MY_PROJECT",
                    "gcps.top": "MY_SUBSCRIPTION_NAME",
                },
            ),
            (
                "kafka-producer",
                "kafka",
                {
                    "kafka.service": "my-topic",
                    "kafka.access": "send",
                },
            ),
        ],
    )
    def test_populate_exit_span_data(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        span_name: str,
        service_name: str,
        attributes: Dict[str, Any],
    ) -> None:
        self.span = InstanaSpan(span_name, span_context, span_processor)
        reg_span = RegisteredSpan(self.span, None, service_name)

        expected_result = {}
        for attr, value in attributes.items():
            attrl = attr.split(".")
            attrl = attrl[1] if len(attrl) > 1 else attrl[0]
            expected_result[attrl] = value

        self.span.set_attributes(attributes)
        reg_span._populate_exit_span_data(self.span)

        for attr, value in expected_result.items():
            assert value == reg_span.data[service_name][attr]

    @pytest.mark.parametrize(
        "attributes",
        [
            {
                "op": "test",
                "http.host": "localhost",
                "http.url": "https://www.instana.com",
            },
            {
                "payload": {
                    "blah": "bleh",
                    "blih": "bloh",
                },
                "http.host": "localhost",
                "http.url": "https://www.instana.com",
            },
        ],
    )
    def test_populate_exit_span_data_boto3(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        attributes: Dict[str, Any],
    ) -> None:
        span_name = service_name = "boto3"
        expected_result = attributes.copy()

        self.span = InstanaSpan(span_name, span_context, span_processor)
        reg_span = RegisteredSpan(self.span, None, service_name)

        self.span.set_attributes(attributes)
        reg_span._populate_exit_span_data(self.span)

        assert expected_result.pop("http.host", None) == reg_span.data["http"]["host"]
        assert expected_result.pop("http.url", None) == reg_span.data["http"]["url"]

        for attr, value in expected_result.items():
            assert value == reg_span.data[service_name][attr]

    def test_populate_exit_span_data_log(
        self, span_context: SpanContext, span_processor: StanRecorder
    ) -> None:
        span_name = service_name = "log"
        self.span = InstanaSpan(span_name, span_context, span_processor)
        reg_span = RegisteredSpan(self.span, None, service_name)

        excepted_text = "Houston, we have a problem!"
        sample_events = [
            (
                "test_populate_exit_span_data_log_event_with_message",
                {
                    "field1": 1,
                    "field2": "two",
                    "message": excepted_text,
                },
                time.time_ns(),
            ),
            (
                "test_populate_exit_span_data_log_event_with_parameters",
                {
                    "field1": 1,
                    "field2": "two",
                    "parameters": excepted_text,
                },
                time.time_ns(),
            ),
        ]

        for event_name, attributes, timestamp in sample_events:
            self.span.add_event(event_name, attributes, timestamp)

        reg_span._populate_exit_span_data(self.span)

        assert excepted_text == reg_span.data["log"]["message"]
        assert excepted_text == reg_span.data["log"]["parameters"]

        while self.span._events:
            self.span._events.pop()

    def test_collect_kafka_attributes(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-kafka-registered-span"
        attributes = {
            "kafka.service": "my-topic",
            "kafka.access": "send",
        }
        service_name = "test-kafka-registered-service"
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )
        reg_span = RegisteredSpan(self.span, None, service_name)

        excepted_result = {
            "kafka.service": attributes["kafka.service"],
            "kafka.access": attributes["kafka.access"],
        }

        reg_span._collect_kafka_attributes(self.span)

        assert excepted_result["kafka.service"] == reg_span.data["kafka"]["service"]
        assert excepted_result["kafka.access"] == reg_span.data["kafka"]["access"]
