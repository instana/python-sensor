# (c) Copyright IBM Corp. 2025

import pytest

from instana.util.config import (
    is_truthy,
    parse_filtered_endpoints,
    parse_filtered_endpoints_dict,
    parse_service_pair,
)


class TestConfig:
    def test_parse_service_pair(self) -> None:
        test_string = "service1:method1,method2"
        response = parse_service_pair(test_string)
        assert response == ["service1.method1", "service1.method2"]

        test_string = "service1;service2"
        response = parse_filtered_endpoints(test_string)
        assert response == ["service1.*", "service2.*"]

        test_string = "service1"
        response = parse_filtered_endpoints(test_string)
        assert response == ["service1.*"]

        test_string = ";"
        response = parse_filtered_endpoints(test_string)
        assert response == []

        test_string = "service1:method1,method2;;;service2:method1;;"
        response = parse_filtered_endpoints(test_string)
        assert response == [
            "service1.method1",
            "service1.method2",
            "service2.method1",
        ]

        test_string = ""
        response = parse_filtered_endpoints(test_string)
        assert response == []

    def test_parse_filtered_endpoints_string(self) -> None:
        test_string = "service1:method1,method2"
        response = parse_service_pair(test_string)
        assert response == ["service1.method1", "service1.method2"]

        test_string = "service1;service2"
        response = parse_filtered_endpoints(test_string)
        assert response == ["service1.*", "service2.*"]

        test_string = "service1"
        response = parse_filtered_endpoints(test_string)
        assert response == ["service1.*"]

        test_string = ";"
        response = parse_filtered_endpoints(test_string)
        assert response == []

        test_string = "service1:method1,method2;;;service2:method1;;"
        response = parse_filtered_endpoints(test_string)
        assert response == [
            "service1.method1",
            "service1.method2",
            "service2.method1",
        ]

        test_string = ""
        response = parse_filtered_endpoints(test_string)
        assert response == []

    def test_parse_filtered_endpoints_dict(self) -> None:
        test_dict = {
            "exclude": [
                {
                    "name": "test_exclude",
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "equals",
                        }
                    ],
                }
            ],
            "include": [],
        }
        response = parse_filtered_endpoints_dict(test_dict)
        assert response == {
            "exclude": [
                {
                    "name": "test_exclude",
                    "suppression": True,
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "equals",
                        }
                    ],
                }
            ],
            "include": [],
        }

        test_dict = {}
        response = parse_filtered_endpoints_dict(test_dict)
        assert response == {"exclude": [], "include": []}

    def test_parse_filtered_endpoints(self) -> None:
        test_pair = "service1:method1,method2"
        response = parse_filtered_endpoints(test_pair)
        assert response == ["service1.method1", "service1.method2"]

        test_pair = "service1;service2"
        response = parse_filtered_endpoints(test_pair)
        assert response == ["service1.*", "service2.*"]

        test_pair = "service1"
        response = parse_filtered_endpoints(test_pair)
        assert response == ["service1.*"]

        test_pair = ";"
        response = parse_filtered_endpoints(test_pair)
        assert response == []

        test_pair = "service1:method1,method2;;;service2:method1;;"
        response = parse_filtered_endpoints(test_pair)
        assert response == [
            "service1.method1",
            "service1.method2",
            "service2.method1",
        ]

        test_pair = ""
        response = parse_filtered_endpoints(test_pair)
        assert response == []

        test_dict = {
            "exclude": [
                {
                    "name": "test_exclude",
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "equals",
                        }
                    ],
                }
            ],
            "include": [],
        }
        response = parse_filtered_endpoints(test_dict)
        assert response == {
            "exclude": [
                {
                    "name": "test_exclude",
                    "suppression": True,
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "equals",
                        }
                    ],
                }
            ],
            "include": [],
        }

        test_dict = {}
        response = parse_filtered_endpoints(test_dict)
        assert response == {"exclude": [], "include": []}

    @pytest.mark.parametrize(
        "value, expected",
        [
            (True, True),
            (False, False),
            ("True", True),
            ("true", True),
            ("1", True),
            (1, True),
            ("False", False),
            ("false", False),
            ("0", False),
            (0, False),
            (None, False),
            ("TRUE", True),
            ("FALSE", False),
            ("yes", False),  # Only "true" and "1" are considered truthy
            ("no", False),
        ],
    )
    def test_is_truthy(self, value, expected) -> None:
        """Test the is_truthy function with various input values."""
        assert is_truthy(value) == expected
