# (c) Copyright IBM Corp. 2025

import pytest

from instana.util.config import (
    is_truthy,
    parse_filter_rules,
    parse_filter_rules_dict,
    parse_filter_rules_string,
)


class TestConfig:
    def test_parse_filter_rules_string(self) -> None:
        """Test parsing of environment variable string format."""
        # Test single rule with strict match
        intermediate = {
            "exclude": {
                "health": {
                    "name": "health",
                    "attributes": [],
                    "suppression": None,
                }
            },
            "include": {},
        }
        result = parse_filter_rules_string(
            "http.target;/health;strict",
            intermediate,
            "exclude",
            "health",
        )
        assert result["exclude"]["health"]["attributes"] == [
            {"key": "http.target", "values": ["/health"], "match_type": "strict"}
        ]

        # Test multiple values with comma separation
        intermediate = {
            "exclude": {
                "topics": {
                    "name": "topics",
                    "attributes": [],
                    "suppression": None,
                }
            },
            "include": {},
        }
        result = parse_filter_rules_string(
            "kafka.service;topic1,topic2,topic3;strict",
            intermediate,
            "exclude",
            "topics",
        )
        assert result["exclude"]["topics"]["attributes"] == [
            {
                "key": "kafka.service",
                "values": ["topic1", "topic2", "topic3"],
                "match_type": "strict",
            }
        ]

        # Test multiple rules separated by pipe
        intermediate = {
            "exclude": {
                "multi": {
                    "name": "multi",
                    "attributes": [],
                    "suppression": None,
                }
            },
            "include": {},
        }
        result = parse_filter_rules_string(
            "http.target;/health;strict|kafka.service;topic1,topic2;equals",
            intermediate,
            "exclude",
            "multi",
        )
        assert len(result["exclude"]["multi"]["attributes"]) == 2
        assert result["exclude"]["multi"]["attributes"][0] == {
            "key": "http.target",
            "values": ["/health"],
            "match_type": "strict",
        }
        assert result["exclude"]["multi"]["attributes"][1] == {
            "key": "kafka.service",
            "values": ["topic1", "topic2"],
            "match_type": "equals",
        }

        # Test default match_type (should be "strict")
        intermediate = {
            "exclude": {
                "default": {
                    "name": "default",
                    "attributes": [],
                    "suppression": None,
                }
            },
            "include": {},
        }
        result = parse_filter_rules_string(
            "http.url;/api/v1",
            intermediate,
            "exclude",
            "default",
        )
        assert result["exclude"]["default"]["attributes"] == [
            {"key": "http.url", "values": ["/api/v1"], "match_type": "strict"}
        ]

        # Test with whitespace
        intermediate = {
            "exclude": {
                "whitespace": {
                    "name": "whitespace",
                    "attributes": [],
                    "suppression": None,
                }
            },
            "include": {},
        }
        result = parse_filter_rules_string(
            " http.target ; /health , /ready ; strict ",
            intermediate,
            "exclude",
            "whitespace",
        )
        assert result["exclude"]["whitespace"]["attributes"] == [
            {
                "key": "http.target",
                "values": ["/health", "/ready"],
                "match_type": "strict",
            }
        ]

        # Test invalid format (missing values) - should skip
        intermediate = {
            "exclude": {
                "invalid": {
                    "name": "invalid",
                    "attributes": [],
                    "suppression": None,
                }
            },
            "include": {},
        }
        result = parse_filter_rules_string(
            "http.target",
            intermediate,
            "exclude",
            "invalid",
        )
        assert result["exclude"]["invalid"]["attributes"] == []

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
        response = parse_filter_rules_dict(test_dict)
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
        response = parse_filter_rules_dict(test_dict)
        assert response == {"exclude": [], "include": []}

    def test_parse_filtered_endpoints(self) -> None:
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
        response = parse_filter_rules(test_dict)
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
        response = parse_filter_rules(test_dict)
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
