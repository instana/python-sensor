# (c) Copyright IBM Corp. 2025

import pytest

from instana.util.config import (
    is_truthy,
    parse_endpoints_of_service,
    parse_ignored_endpoints,
    parse_ignored_endpoints_dict,
    parse_kafka_methods,
    parse_service_pair,
)


class TestConfig:
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

    def test_parse_kafka_methods_as_dict(self) -> None:
        test_rule_as_dict = {"methods": ["send"], "endpoints": ["topic1"]}
        parsed_rule = parse_kafka_methods(test_rule_as_dict)
        assert parsed_rule == ["kafka.send.topic1"]

    def test_parse_kafka_methods_as_str(self) -> None:
        test_rule_as_str = ["send"]
        parsed_rule = parse_kafka_methods(test_rule_as_str)
        assert parsed_rule == ["kafka.send.*"]

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


class TestSpanFilterConfig:
    """Tests for span filter configuration parsing functions."""

    @pytest.mark.parametrize(
        "attr,expected_valid,expected_match_type",
        [
            (
                {"key": "type", "values": ["redis", "mysql"], "match_type": "strict"},
                True,
                "strict",
            ),
            ({"key": "category", "values": ["databases"]}, True, "strict"),
            (
                {"key": "type", "values": ["redis"], "match_type": "invalid"},
                True,
                "strict",
            ),
            ({"values": ["redis"], "match_type": "strict"}, False, None),
            ({"key": "type", "match_type": "strict"}, False, None),
        ],
    )
    def test_parse_filter_attribute(
        self, attr, expected_valid, expected_match_type
    ) -> None:
        """Test filter attribute parsing with various inputs."""
        from instana.util.config import parse_filter_attribute

        result = parse_filter_attribute(attr, "test_rule")
        if expected_valid:
            assert result is not None
            assert result["match_type"] == expected_match_type
            assert result["key"] == attr["key"]
            assert result["values"] == attr["values"]
        else:
            assert result is None

    @pytest.mark.parametrize(
        "policy,rule,expected_name,expected_suppression,expected_attr_count",
        [
            (
                "exclude",
                {
                    "name": "Exclude Redis",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"}
                    ],
                },
                "Exclude Redis",
                True,
                1,
            ),
            (
                "include",
                {
                    "name": "Include Redis GET",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["GET"],
                            "match_type": "strict",
                        },
                    ],
                },
                "Include Redis GET",
                None,
                2,
            ),
        ],
    )
    def test_parse_filter_rule_valid(
        self, policy, rule, expected_name, expected_suppression, expected_attr_count
    ) -> None:
        """Test valid filter rule parsing for exclude and include policies."""
        from instana.util.config import parse_filter_rule

        result = parse_filter_rule(rule, policy)
        assert result["name"] == expected_name
        assert result["suppression"] == expected_suppression
        assert len(result["attributes"]) == expected_attr_count

    @pytest.mark.parametrize(
        "rule",
        [
            {"attributes": [{"key": "type", "values": ["redis"]}]},
            {"name": "Test Rule"},
            {
                "name": "Test Rule",
                "attributes": [
                    {"values": ["redis"]},
                    {"key": "type"},
                ],
            },
        ],
    )
    def test_parse_filter_rule_errors(self, rule) -> None:
        """Test filter rule error handling for missing/invalid fields."""
        from instana.util.config import parse_filter_rule

        result = parse_filter_rule(rule, "exclude")
        assert result is None

    def test_parse_span_filter_config_basic(self) -> None:
        """Test basic config parsing: deactivated, empty, and invalid types."""
        from instana.util.config import parse_span_filter_config

        # Deactivated
        config = {"deactivate": True}
        result = parse_span_filter_config(config)
        assert result == {"deactivated": True}

        # Empty
        config = {}
        result = parse_span_filter_config(config)
        assert result["deactivated"] is False
        assert result["exclude"] == []
        assert result["include"] == []

        # Invalid type
        result = parse_span_filter_config("invalid")
        assert result == {}

    def test_parse_span_filter_config_policies(self) -> None:
        """Test exclude, include, and both policies."""
        from instana.util.config import parse_span_filter_config

        # Exclude only
        config = {
            "exclude": [
                {
                    "name": "Exclude Redis",
                    "attributes": [{"key": "type", "values": ["redis"]}],
                }
            ]
        }
        result = parse_span_filter_config(config)
        assert result["deactivated"] is False
        assert len(result["exclude"]) == 1
        assert result["exclude"][0]["name"] == "Exclude Redis"

        # Include only
        config = {
            "include": [
                {
                    "name": "Include Redis GET",
                    "attributes": [
                        {"key": "type", "values": ["redis"]},
                        {"key": "redis.command", "values": ["GET"]},
                    ],
                }
            ]
        }
        result = parse_span_filter_config(config)
        assert result["deactivated"] is False
        assert len(result["include"]) == 1
        assert result["include"][0]["name"] == "Include Redis GET"

        # Both policies
        config = {
            "exclude": [
                {
                    "name": "Exclude all Redis",
                    "attributes": [{"key": "type", "values": ["redis"]}],
                }
            ],
            "include": [
                {
                    "name": "Include Redis GET",
                    "attributes": [
                        {"key": "type", "values": ["redis"]},
                        {"key": "redis.command", "values": ["GET"]},
                    ],
                }
            ],
        }
        result = parse_span_filter_config(config)
        assert result["deactivated"] is False
        assert len(result["exclude"]) == 1
        assert len(result["include"]) == 1

    def test_parse_span_filter_config_match_types(self) -> None:
        """Test all supported match types."""
        from instana.util.config import parse_span_filter_config

        config = {
            "exclude": [
                {
                    "name": "Test Match Types",
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/api"],
                            "match_type": "startswith",
                        },
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "endswith",
                        },
                        {
                            "key": "http.url",
                            "values": ["admin"],
                            "match_type": "contains",
                        },
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                    ],
                }
            ]
        }
        result = parse_span_filter_config(config)
        attrs = result["exclude"][0]["attributes"]
        assert attrs[0]["match_type"] == "startswith"
        assert attrs[1]["match_type"] == "endswith"
        assert attrs[2]["match_type"] == "contains"


class TestSpanFilterEnvVars:
    """Tests for environment variable-based span filter configuration."""

    @pytest.mark.parametrize(
        "rule_str,expected_key,expected_values,expected_match",
        [
            ("http.target;/health", "http.target", ["/health"], "strict"),
            ("http.target;/api;startswith", "http.target", ["/api"], "startswith"),
            (
                "http.target;/health,/ready,/status",
                "http.target",
                ["/health", "/ready", "/status"],
                "strict",
            ),
            ("http.url;/test;strict", "http.url", ["/test"], "strict"),
            ("http.url;/test;startswith", "http.url", ["/test"], "startswith"),
            ("http.url;/test;endswith", "http.url", ["/test"], "endswith"),
            ("http.url;/test;contains", "http.url", ["/test"], "contains"),
            ("http.target;/health;invalid", "http.target", ["/health"], "strict"),
        ],
    )
    def test_parse_env_filter_rule_valid(
        self, rule_str, expected_key, expected_values, expected_match
    ) -> None:
        """Test environment filter rule parsing with various valid inputs."""
        from instana.util.config import parse_env_filter_rule

        rule = parse_env_filter_rule(rule_str)
        assert rule is not None
        assert rule["key"] == expected_key
        assert rule["values"] == expected_values
        assert rule["match_type"] == expected_match

    @pytest.mark.parametrize(
        "invalid_rule",
        [
            "http.target",
            "",
            ";/health",
            "http.target;",
        ],
    )
    def test_parse_env_filter_rule_invalid(self, invalid_rule) -> None:
        """Test invalid rule formats return None."""
        from instana.util.config import parse_env_filter_rule

        assert parse_env_filter_rule(invalid_rule) is None

    def test_group_env_filter_vars(self, monkeypatch) -> None:
        """Test grouping of environment variables"""
        from instana.util.config import group_env_filter_vars

        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "http.target;/health"
        )
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_SUPPRESSION", "false")
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_1_ATTRIBUTES", "type;redis")
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES", "redis.command;GET"
        )

        grouped = group_env_filter_vars()

        assert "exclude" in grouped
        assert "include" in grouped
        assert "0" in grouped["exclude"]
        assert "1" in grouped["exclude"]
        assert "0" in grouped["include"]
        assert grouped["exclude"]["0"]["attributes"] == "http.target;/health"
        assert grouped["exclude"]["0"]["suppression"] == "false"
        assert grouped["exclude"]["1"]["attributes"] == "type;redis"
        assert grouped["include"]["0"]["attributes"] == "redis.command;GET"

    @pytest.mark.parametrize(
        "policy,env_data,expected_name,expected_suppression,expected_attr_count",
        [
            (
                "exclude",
                {
                    "attributes": "http.target;/health;startswith",
                    "suppression": "false",
                },
                "env_filter_exclude_0",
                False,
                1,
            ),
            (
                "include",
                {"attributes": "type;redis|redis.command;GET"},
                "env_filter_include_0",
                None,
                2,
            ),
            (
                "exclude",
                {"attributes": "type;kafka|kafka.service;topic1,topic2;contains"},
                "env_filter_exclude_0",
                True,
                2,
            ),
            (
                "exclude",
                {"attributes": "type;redis"},
                "env_filter_exclude_0",
                True,
                1,
            ),
        ],
    )
    def test_build_filter_rule_from_env_valid(
        self, policy, env_data, expected_name, expected_suppression, expected_attr_count
    ) -> None:
        """Test building filter rules from environment data."""
        from instana.util.config import build_filter_rule_from_env

        rule = build_filter_rule_from_env("0", env_data, policy)

        assert rule is not None
        assert rule["name"] == expected_name
        assert rule["suppression"] == expected_suppression
        assert len(rule["attributes"]) == expected_attr_count

    def test_build_filter_rule_from_env_missing_attributes(self) -> None:
        """Test that missing attributes returns None."""
        from instana.util.config import build_filter_rule_from_env

        env_data = {"suppression": "true"}
        rule = build_filter_rule_from_env("0", env_data, "exclude")
        assert rule is None

    def test_parse_span_filter_from_env_policies(self, monkeypatch) -> None:
        """Test exclude, include, and both policies from environment."""
        from instana.util.config import parse_span_filter_from_env

        # Test exclude only
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "http.target;/health"
        )
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_1_ATTRIBUTES", "type;redis")

        config = parse_span_filter_from_env()
        assert config["deactivated"] is False
        assert len(config["exclude"]) == 2
        assert len(config["include"]) == 0

        # Clean up
        monkeypatch.delenv("INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES")
        monkeypatch.delenv("INSTANA_TRACING_FILTER_EXCLUDE_1_ATTRIBUTES")

        # Test include only
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES",
            "type;redis|redis.command;GET",
        )

        config = parse_span_filter_from_env()
        assert len(config["exclude"]) == 0
        assert len(config["include"]) == 1
        assert len(config["include"][0]["attributes"]) == 2

        # Clean up
        monkeypatch.delenv("INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES")

        # Test both policies
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "type;redis")
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES",
            "type;redis|redis.command;GET",
        )

        config = parse_span_filter_from_env()
        assert len(config["exclude"]) == 1
        assert len(config["include"]) == 1

    def test_parse_span_filter_from_env_suppression(self, monkeypatch) -> None:
        """Test suppression flag handling with various truthy values."""
        from instana.util.config import parse_span_filter_from_env

        # Test false suppression
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "type;kafka")
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_SUPPRESSION", "false")

        config = parse_span_filter_from_env()
        assert config["exclude"][0]["suppression"] is False

        # Clean up
        monkeypatch.delenv("INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES")
        monkeypatch.delenv("INSTANA_TRACING_FILTER_EXCLUDE_0_SUPPRESSION")

        # Test various truthy values
        for value in ["true", "True", "1"]:
            monkeypatch.setenv(
                "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "type;redis"
            )
            monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_SUPPRESSION", value)

            config = parse_span_filter_from_env()
            assert config["exclude"][0]["suppression"] is True

            monkeypatch.delenv("INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES")
            monkeypatch.delenv("INSTANA_TRACING_FILTER_EXCLUDE_0_SUPPRESSION")

    def test_parse_span_filter_from_env_empty(self) -> None:
        """Test parsing when no env vars are set."""
        from instana.util.config import parse_span_filter_from_env

        config = parse_span_filter_from_env()

        assert config["deactivated"] is False
        assert config["exclude"] == []
        assert config["include"] == []

    def test_parse_span_filter_from_env_complex_example(self, monkeypatch) -> None:
        """Test complex real-world example"""
        from instana.util.config import parse_span_filter_from_env

        # Exclude health checks
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES",
            "http.target;/health,/ready;startswith",
        )
        # Exclude specific Kafka topics
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_1_ATTRIBUTES",
            "type;kafka|kafka.service;internal-topic;contains",
        )
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_1_SUPPRESSION", "false")
        # Include only Redis GET commands
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES",
            "type;redis|redis.command;GET,MGET",
        )

        config = parse_span_filter_from_env()

        assert len(config["exclude"]) == 2
        assert len(config["include"]) == 1
        assert config["exclude"][0]["attributes"][0]["match_type"] == "startswith"
        assert config["exclude"][1]["suppression"] is False
        assert config["include"][0]["attributes"][1]["values"] == ["GET", "MGET"]
