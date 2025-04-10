import logging
from typing import Generator

import pytest

from instana.util.config import (
    parse_endpoints_of_service,
    parse_ignored_endpoints,
    parse_ignored_endpoints_dict,
    parse_ignored_endpoints_from_yaml,
    parse_service_pair,
)


class TestConfig:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield

    def test_parse_service_pair(self) -> None:
        test_string = "service1:method1,method2"
        response = parse_service_pair(test_string)
        assert response == ["service1.method1", "service1.method2"]

        test_string = "service1;service2"
        response = parse_ignored_endpoints(test_string)
        assert response == ["service1.*", "service2.*"]

        test_string = "service1"
        response = parse_ignored_endpoints(test_string)
        assert response == ["service1.*"]

        test_string = ";"
        response = parse_ignored_endpoints(test_string)
        assert response == []

        test_string = "service1:method1,method2;;;service2:method1;;"
        response = parse_ignored_endpoints(test_string)
        assert response == [
            "service1.method1",
            "service1.method2",
            "service2.method1",
        ]

        test_string = ""
        response = parse_ignored_endpoints(test_string)
        assert response == []

    def test_parse_ignored_endpoints_string(self) -> None:
        test_string = "service1:method1,method2"
        response = parse_service_pair(test_string)
        assert response == ["service1.method1", "service1.method2"]

        test_string = "service1;service2"
        response = parse_ignored_endpoints(test_string)
        assert response == ["service1.*", "service2.*"]

        test_string = "service1"
        response = parse_ignored_endpoints(test_string)
        assert response == ["service1.*"]

        test_string = ";"
        response = parse_ignored_endpoints(test_string)
        assert response == []

        test_string = "service1:method1,method2;;;service2:method1;;"
        response = parse_ignored_endpoints(test_string)
        assert response == [
            "service1.method1",
            "service1.method2",
            "service2.method1",
        ]

        test_string = ""
        response = parse_ignored_endpoints(test_string)
        assert response == []

    def test_parse_ignored_endpoints_dict(self) -> None:
        test_dict = {"service1": ["method1", "method2"]}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == ["service1.method1", "service1.method2"]

        test_dict = {"SERVICE1": ["method1", "method2"]}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == ["service1.method1", "service1.method2"]

        test_dict = {"service1": [], "service2": []}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == ["service1.*", "service2.*"]

        test_dict = {"service1": []}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == ["service1.*"]

        test_dict = {}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == []

    def test_parse_ignored_endpoints(self) -> None:
        test_pair = "service1:method1,method2"
        response = parse_ignored_endpoints(test_pair)
        assert response == ["service1.method1", "service1.method2"]

        test_pair = "service1;service2"
        response = parse_ignored_endpoints(test_pair)
        assert response == ["service1.*", "service2.*"]

        test_pair = "service1"
        response = parse_ignored_endpoints(test_pair)
        assert response == ["service1.*"]

        test_pair = ";"
        response = parse_ignored_endpoints(test_pair)
        assert response == []

        test_pair = "service1:method1,method2;;;service2:method1;;"
        response = parse_ignored_endpoints(test_pair)
        assert response == [
            "service1.method1",
            "service1.method2",
            "service2.method1",
        ]

        test_pair = ""
        response = parse_ignored_endpoints(test_pair)
        assert response == []

        test_dict = {"service1": ["method1", "method2"]}
        response = parse_ignored_endpoints(test_dict)
        assert response == ["service1.method1", "service1.method2"]

        test_dict = {"service1": [], "service2": []}
        response = parse_ignored_endpoints(test_dict)
        assert response == ["service1.*", "service2.*"]

        test_dict = {"service1": []}
        response = parse_ignored_endpoints(test_dict)
        assert response == ["service1.*"]

        test_dict = {}
        response = parse_ignored_endpoints(test_dict)
        assert response == []

    def test_parse_endpoints_of_service(self) -> None:
        test_ignore_endpoints = {
            "service1": ["method1", "method2"],
            "service2": ["method3", "method4"],
            "kafka": [
                {
                    "methods": ["method5", "method6"],
                    "endpoints": ["endpoint1", "endpoint2"],
                }
            ],
        }
        ignore_endpoints = []
        for service, methods in test_ignore_endpoints.items():
            ignore_endpoints.extend(parse_endpoints_of_service([], service, methods))
        assert ignore_endpoints == [
            "service1.method1",
            "service1.method2",
            "service2.method3",
            "service2.method4",
            "kafka.method5.endpoint1",
            "kafka.method5.endpoint2",
            "kafka.method6.endpoint1",
            "kafka.method6.endpoint2",
        ]

    def test_parse_ignored_endpoints_from_yaml(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")

        # test with tracing
        ignored_endpoints = parse_ignored_endpoints_from_yaml(
            "tests/util/test_configuration-1.yaml"
        )
        assert ignored_endpoints == [
            "redis.get",
            "redis.type",
            "dynamodb.query",
            "kafka.consume.span-topic",
            "kafka.consume.topic1",
            "kafka.consume.topic2",
            "kafka.send.span-topic",
            "kafka.send.topic1",
            "kafka.send.topic2",
            "kafka.consume.topic3",
            "kafka.*.span-topic",
            "kafka.*.topic4",
        ]

        # test with com.instana.tracing
        ignored_endpoints = parse_ignored_endpoints_from_yaml(
            "tests/util/test_configuration-2.yaml"
        )
        assert ignored_endpoints == [
            "redis.get",
            "redis.type",
            "dynamodb.query",
            "kafka.consume.span-topic",
            "kafka.consume.topic1",
            "kafka.consume.topic2",
            "kafka.send.span-topic",
            "kafka.send.topic1",
            "kafka.send.topic2",
            "kafka.consume.topic3",
            "kafka.*.span-topic",
            "kafka.*.topic4",
        ]
        assert (
            'Please use "tracing" instead of "com.instana.tracing"' in caplog.messages
        )
