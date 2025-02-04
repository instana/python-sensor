from typing import Generator

import pytest

from instana.util.config import (
    parse_ignored_endpoints,
    parse_ignored_endpoints_dict,
    parse_service_pair,
)


class TestConfig:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield

    def test_parse_service_pair(self) -> None:
        test_string = "service1:endpoint1,endpoint2"
        response = parse_service_pair(test_string)
        assert response == ["service1.endpoint1", "service1.endpoint2"]

        test_string = "service1;service2"
        response = parse_ignored_endpoints(test_string)
        assert response == ["service1", "service2"]

        test_string = "service1"
        response = parse_ignored_endpoints(test_string)
        assert response == ["service1"]

        test_string = ";"
        response = parse_ignored_endpoints(test_string)
        assert response == []

        test_string = "service1:endpoint1,endpoint2;;;service2:endpoint1;;"
        response = parse_ignored_endpoints(test_string)
        assert response == [
            "service1.endpoint1",
            "service1.endpoint2",
            "service2.endpoint1",
        ]

        test_string = ""
        response = parse_ignored_endpoints(test_string)
        assert response == []

    def test_parse_ignored_endpoints_string(self) -> None:
        test_string = "service1:endpoint1,endpoint2"
        response = parse_service_pair(test_string)
        assert response == ["service1.endpoint1", "service1.endpoint2"]

        test_string = "service1;service2"
        response = parse_ignored_endpoints(test_string)
        assert response == ["service1", "service2"]

        test_string = "service1"
        response = parse_ignored_endpoints(test_string)
        assert response == ["service1"]

        test_string = ";"
        response = parse_ignored_endpoints(test_string)
        assert response == []

        test_string = "service1:endpoint1,endpoint2;;;service2:endpoint1;;"
        response = parse_ignored_endpoints(test_string)
        assert response == [
            "service1.endpoint1",
            "service1.endpoint2",
            "service2.endpoint1",
        ]

        test_string = ""
        response = parse_ignored_endpoints(test_string)
        assert response == []

    def test_parse_ignored_endpoints_dict(self) -> None:
        test_dict = {"service1": ["endpoint1", "endpoint2"]}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == ["service1.endpoint1", "service1.endpoint2"]

        test_dict = {"SERVICE1": ["ENDPOINT1", "ENDPOINT2"]}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == ["service1.endpoint1", "service1.endpoint2"]

        test_dict = {"service1": [], "service2": []}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == ["service1", "service2"]

        test_dict = {"service1": []}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == ["service1"]

        test_dict = {}
        response = parse_ignored_endpoints_dict(test_dict)
        assert response == []

    def test_parse_ignored_endpoints(self) -> None:
        test_pair = "service1:endpoint1,endpoint2"
        response = parse_ignored_endpoints(test_pair)
        assert response == ["service1.endpoint1", "service1.endpoint2"]

        test_pair = "service1;service2"
        response = parse_ignored_endpoints(test_pair)
        assert response == ["service1", "service2"]

        test_pair = "service1"
        response = parse_ignored_endpoints(test_pair)
        assert response == ["service1"]

        test_pair = ";"
        response = parse_ignored_endpoints(test_pair)
        assert response == []

        test_pair = "service1:endpoint1,endpoint2;;;service2:endpoint1;;"
        response = parse_ignored_endpoints(test_pair)
        assert response == [
            "service1.endpoint1",
            "service1.endpoint2",
            "service2.endpoint1",
        ]

        test_pair = ""
        response = parse_ignored_endpoints(test_pair)
        assert response == []

        test_dict = {"service1": ["endpoint1", "endpoint2"]}
        response = parse_ignored_endpoints(test_dict)
        assert response == ["service1.endpoint1", "service1.endpoint2"]

        test_dict = {"service1": [], "service2": []}
        response = parse_ignored_endpoints(test_dict)
        assert response == ["service1", "service2"]

        test_dict = {"service1": []}
        response = parse_ignored_endpoints(test_dict)
        assert response == ["service1"]

        test_dict = {}
        response = parse_ignored_endpoints(test_dict)
        assert response == []
