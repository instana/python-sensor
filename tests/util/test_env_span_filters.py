# (C) Copyright IBM Corp. 2026.

"""
Tests for environment variable-based span filter configuration.
"""

import os

from instana.util.config import (
    parse_env_filter_rule,
    group_env_filter_vars,
    build_filter_rule_from_env,
    parse_span_filter_from_env,
)


class TestParseEnvFilterRule:
    """Tests for parse_env_filter_rule() function."""

    def test_simple_rule(self) -> None:
        """Test parsing simple rule: key;values"""
        result = parse_env_filter_rule("http.target;/health")
        assert result == {
            "key": "http.target",
            "values": ["/health"],
            "match_type": "strict",
        }

    def test_rule_with_match_type(self) -> None:
        """Test parsing rule with match_type: key;values;match_type"""
        result = parse_env_filter_rule("http.target;/api;startswith")
        assert result == {
            "key": "http.target",
            "values": ["/api"],
            "match_type": "startswith",
        }

    def test_rule_with_multiple_values(self) -> None:
        """Test parsing rule with comma-separated values"""
        result = parse_env_filter_rule("http.target;/health,/ready,/metrics")
        assert result == {
            "key": "http.target",
            "values": ["/health", "/ready", "/metrics"],
            "match_type": "strict",
        }

    def test_rule_with_all_match_types(self) -> None:
        """Test all valid match_type values"""
        for match_type in ["strict", "startswith", "endswith", "contains"]:
            result = parse_env_filter_rule(f"type;redis;{match_type}")
            assert result["match_type"] == match_type

    def test_invalid_match_type_defaults_to_strict(self) -> None:
        """Test that invalid match_type defaults to 'strict'"""
        result = parse_env_filter_rule("type;redis;invalid_type")
        assert result["match_type"] == "strict"

    def test_invalid_format_missing_values(self) -> None:
        """Test handling of invalid rule format (missing values)"""
        result = parse_env_filter_rule("http.target")
        assert result is None

    def test_invalid_format_empty_string(self) -> None:
        """Test handling of empty string"""
        result = parse_env_filter_rule("")
        assert result is None

    def test_invalid_format_none(self) -> None:
        """Test handling of None"""
        result = parse_env_filter_rule(None)
        assert result is None

    def test_empty_key(self) -> None:
        """Test handling of empty key"""
        result = parse_env_filter_rule(";/health")
        assert result is None

    def test_empty_values(self) -> None:
        """Test handling of empty values"""
        result = parse_env_filter_rule("http.target;")
        assert result is None

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is properly trimmed"""
        result = parse_env_filter_rule("  http.target  ;  /health  ;  startswith  ")
        assert result == {
            "key": "http.target",
            "values": ["/health"],
            "match_type": "startswith",
        }

    def test_values_with_commas_and_spaces(self) -> None:
        """Test values with mixed commas and spaces"""
        result = parse_env_filter_rule("type;redis, mysql , postgresql")
        assert result == {
            "key": "type",
            "values": ["redis", "mysql", "postgresql"],
            "match_type": "strict",
        }


class TestGroupEnvFilterVars:
    """Tests for group_env_filter_vars() function."""

    def test_group_exclude_attributes(self, monkeypatch) -> None:
        """Test grouping exclude attributes"""
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "http.target;/health"
        )
        result = group_env_filter_vars()
        assert "exclude" in result
        assert "0" in result["exclude"]
        assert result["exclude"]["0"]["attributes"] == "http.target;/health"

    def test_group_include_attributes(self, monkeypatch) -> None:
        """Test grouping include attributes"""
        monkeypatch.setenv("INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES", "type;redis")
        result = group_env_filter_vars()
        assert "include" in result
        assert "0" in result["include"]
        assert result["include"]["0"]["attributes"] == "type;redis"

    def test_group_with_suppression(self, monkeypatch) -> None:
        """Test grouping with suppression flag"""
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "type;kafka")
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_SUPPRESSION", "false")
        result = group_env_filter_vars()
        assert result["exclude"]["0"]["attributes"] == "type;kafka"
        assert result["exclude"]["0"]["suppression"] == "false"

    def test_group_multiple_rules(self, monkeypatch) -> None:
        """Test grouping multiple rules"""
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "http.target;/health"
        )
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_1_ATTRIBUTES", "type;redis")
        monkeypatch.setenv("INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES", "type;mysql")
        result = group_env_filter_vars()
        assert "0" in result["exclude"]
        assert "1" in result["exclude"]
        assert "0" in result["include"]

    def test_ignore_invalid_policy(self, monkeypatch) -> None:
        """Test that invalid policy is ignored"""
        monkeypatch.setenv("INSTANA_TRACING_FILTER_INVALID_0_ATTRIBUTES", "type;redis")
        result = group_env_filter_vars()
        assert "0" not in result.get("invalid", {})

    def test_ignore_invalid_field(self, monkeypatch) -> None:
        """Test that invalid field is ignored"""
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_INVALID", "value")
        result = group_env_filter_vars()
        assert "invalid" not in result["exclude"].get("0", {})

    def test_ignore_malformed_env_vars(self, monkeypatch) -> None:
        """Test that malformed env vars are ignored"""
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE", "value")
        monkeypatch.setenv("INSTANA_TRACING_FILTER_", "value")
        result = group_env_filter_vars()
        # Should not crash, just ignore invalid vars
        assert isinstance(result, dict)

    def test_empty_environment(self) -> None:
        """Test with no INSTANA_TRACING_FILTER_* vars"""
        # Clear any existing env vars
        for key in list(os.environ.keys()):
            if key.startswith("INSTANA_TRACING_FILTER_"):
                del os.environ[key]
        result = group_env_filter_vars()
        assert result == {"exclude": {}, "include": {}}


class TestBuildFilterRuleFromEnv:
    """Tests for build_filter_rule_from_env() function."""

    def test_build_simple_exclude_rule(self) -> None:
        """Test building simple exclude rule"""
        env_data = {"attributes": "http.target;/health"}
        result = build_filter_rule_from_env("0", env_data, "exclude")
        assert result == {
            "name": "env_filter_exclude_0",
            "attributes": [
                {"key": "http.target", "values": ["/health"], "match_type": "strict"}
            ],
            "suppression": True,
        }

    def test_build_include_rule(self) -> None:
        """Test building include rule"""
        env_data = {"attributes": "type;redis"}
        result = build_filter_rule_from_env("0", env_data, "include")
        assert result == {
            "name": "env_filter_include_0",
            "attributes": [
                {"key": "type", "values": ["redis"], "match_type": "strict"}
            ],
            "suppression": None,
        }

    def test_build_rule_with_multiple_attributes(self) -> None:
        """Test building rule with pipe-separated attributes"""
        env_data = {"attributes": "type;redis|redis.command;GET"}
        result = build_filter_rule_from_env("1", env_data, "exclude")
        assert result["name"] == "env_filter_exclude_1"
        assert len(result["attributes"]) == 2
        assert result["attributes"][0] == {
            "key": "type",
            "values": ["redis"],
            "match_type": "strict",
        }
        assert result["attributes"][1] == {
            "key": "redis.command",
            "values": ["GET"],
            "match_type": "strict",
        }

    def test_build_rule_with_suppression_false(self) -> None:
        """Test building rule with suppression=false"""
        env_data = {"attributes": "type;kafka", "suppression": "false"}
        result = build_filter_rule_from_env("0", env_data, "exclude")
        assert result["suppression"] is False

    def test_build_rule_with_suppression_true(self) -> None:
        """Test building rule with suppression=true"""
        env_data = {"attributes": "type;kafka", "suppression": "true"}
        result = build_filter_rule_from_env("0", env_data, "exclude")
        assert result["suppression"] is True

    def test_build_rule_suppression_default(self) -> None:
        """Test that suppression defaults to True for exclude"""
        env_data = {"attributes": "type;kafka"}
        result = build_filter_rule_from_env("0", env_data, "exclude")
        assert result["suppression"] is True

    def test_missing_attributes_returns_none(self) -> None:
        """Test that missing attributes returns None"""
        env_data = {"suppression": "false"}
        result = build_filter_rule_from_env("0", env_data, "exclude")
        assert result is None

    def test_invalid_attributes_returns_none(self) -> None:
        """Test that invalid attributes returns None"""
        env_data = {"attributes": "invalid"}
        result = build_filter_rule_from_env("0", env_data, "exclude")
        assert result is None

    def test_empty_attributes_returns_none(self) -> None:
        """Test that empty attributes returns None"""
        env_data = {"attributes": ""}
        result = build_filter_rule_from_env("0", env_data, "exclude")
        assert result is None

    def test_whitespace_in_pipe_separated_attributes(self) -> None:
        """Test handling of whitespace in pipe-separated attributes"""
        env_data = {"attributes": "type;redis | redis.command;GET | redis.db;0"}
        result = build_filter_rule_from_env("0", env_data, "exclude")
        assert len(result["attributes"]) == 3


class TestParseSpanFilterFromEnv:
    """Tests for parse_span_filter_from_env() function."""

    def test_parse_single_exclude_rule(self, monkeypatch) -> None:
        """Test parsing single exclude rule"""
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "http.target;/health"
        )
        result = parse_span_filter_from_env()
        assert result["deactivated"] is False
        assert len(result["exclude"]) == 1
        assert result["exclude"][0]["name"] == "env_filter_exclude_0"
        assert len(result["exclude"][0]["attributes"]) == 1

    def test_parse_single_include_rule(self, monkeypatch) -> None:
        """Test parsing single include rule"""
        monkeypatch.setenv("INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES", "type;redis")
        result = parse_span_filter_from_env()
        assert result["deactivated"] is False
        assert len(result["include"]) == 1
        assert result["include"][0]["name"] == "env_filter_include_0"

    def test_parse_multiple_exclude_rules(self, monkeypatch) -> None:
        """Test parsing multiple exclude rules"""
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "http.target;/health"
        )
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_1_ATTRIBUTES",
            "type;redis|redis.command;GET",
        )
        result = parse_span_filter_from_env()
        assert len(result["exclude"]) == 2
        assert result["exclude"][0]["name"] == "env_filter_exclude_0"
        assert result["exclude"][1]["name"] == "env_filter_exclude_1"

    def test_parse_with_suppression(self, monkeypatch) -> None:
        """Test parsing with suppression flag"""
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "type;kafka")
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_0_SUPPRESSION", "false")
        result = parse_span_filter_from_env()
        assert result["exclude"][0]["suppression"] is False

    def test_parse_mixed_policies(self, monkeypatch) -> None:
        """Test parsing both exclude and include rules"""
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "http.target;/health"
        )
        monkeypatch.setenv("INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES", "type;redis")
        result = parse_span_filter_from_env()
        assert len(result["exclude"]) == 1
        assert len(result["include"]) == 1

    def test_parse_empty_environment(self) -> None:
        """Test parsing with no env vars"""
        # Clear any existing env vars
        for key in list(os.environ.keys()):
            if key.startswith("INSTANA_TRACING_FILTER_"):
                del os.environ[key]
        result = parse_span_filter_from_env()
        assert result == {"deactivated": False, "exclude": [], "include": []}

    def test_parse_complex_example(self, monkeypatch) -> None:
        """Test parsing complex real-world example"""
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES", "http.target;/health"
        )
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_1_ATTRIBUTES",
            "type;redis|redis.command;GET,SET",
        )
        monkeypatch.setenv("INSTANA_TRACING_FILTER_EXCLUDE_1_SUPPRESSION", "false")
        monkeypatch.setenv(
            "INSTANA_TRACING_FILTER_EXCLUDE_2_ATTRIBUTES",
            "http.target;/api;startswith",
        )
        monkeypatch.setenv("INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES", "type;mysql")

        result = parse_span_filter_from_env()

        # Verify structure
        assert result["deactivated"] is False
        assert len(result["exclude"]) == 3
        assert len(result["include"]) == 1

        # Verify exclude rule 0
        assert result["exclude"][0]["name"] == "env_filter_exclude_0"
        assert result["exclude"][0]["suppression"] is True
        assert len(result["exclude"][0]["attributes"]) == 1

        # Verify exclude rule 1 (multiple attributes)
        assert result["exclude"][1]["name"] == "env_filter_exclude_1"
        assert result["exclude"][1]["suppression"] is False
        assert len(result["exclude"][1]["attributes"]) == 2
        assert result["exclude"][1]["attributes"][1]["values"] == ["GET", "SET"]

        # Verify exclude rule 2 (with match_type)
        assert result["exclude"][2]["name"] == "env_filter_exclude_2"
        assert result["exclude"][2]["attributes"][0]["match_type"] == "startswith"

        # Verify include rule
        assert result["include"][0]["name"] == "env_filter_include_0"
        assert result["include"][0]["suppression"] is None


# Made with Bob
