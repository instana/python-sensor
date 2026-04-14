# (c) Copyright IBM Corp. 2025

from collections import defaultdict

from instana.util.span_utils import (
    get_span_kind,
    match_key_filter,
    matches_rule,
    resolve_nested_key,
)


class TestSpanUtils:
    def test_get_span_kind(self) -> None:
        assert get_span_kind(1) == "entry"
        assert get_span_kind(2) == "exit"
        assert get_span_kind(3) == "intermediate"
        assert get_span_kind("foo") == "intermediate"

    def test_match_key_filter(self) -> None:
        # Strict
        assert match_key_filter("foo", "foo", "strict")
        assert not match_key_filter("foo", "bar", "strict")

        # Contains
        assert match_key_filter("foobar", "oba", "contains")
        assert not match_key_filter("foobar", "baz", "contains")

        # Startswith
        assert match_key_filter("foobar", "foo", "startswith")
        assert not match_key_filter("foobar", "bar", "startswith")

        # Endswith
        assert match_key_filter("foobar", "bar", "endswith")
        assert not match_key_filter("foobar", "foo", "endswith")

        # Wildcard
        assert match_key_filter("whatever", "*", "strict")
        assert match_key_filter("whatever", "*", "contains")

    def test_matches_rule_category(self) -> None:
        # Redis is in databases category
        span_attrs = {"type": "redis"}

        rule_positive = [{"key": "category", "values": ["databases"]}]
        assert matches_rule(rule_positive, span_attrs)

        rule_negative = [{"key": "category", "values": ["messaging"]}]
        assert not matches_rule(rule_negative, span_attrs)

        # Unknown type
        span_attrs_unknown = {"type": "unknown_db"}
        assert not matches_rule(rule_positive, span_attrs_unknown)

    def test_matches_rule_kind(self) -> None:
        span_attrs_entry = {"kind": 1}

        rule_entry = [{"key": "kind", "values": ["entry"]}]
        assert matches_rule(rule_entry, span_attrs_entry)

        rule_exit = [{"key": "kind", "values": ["exit"]}]
        assert not matches_rule(rule_exit, span_attrs_entry)

    def test_matches_rule_type(self) -> None:
        span_attrs = {"type": "http"}

        rule_http = [{"key": "type", "values": ["http"]}]
        assert matches_rule(rule_http, span_attrs)

        rule_rpc = [{"key": "type", "values": ["rpc"]}]
        assert not matches_rule(rule_rpc, span_attrs)

    def test_matches_rule_attributes(self) -> None:
        span_attrs = {"http.url": "http://example.com/health", "http.status_code": 200}

        # Strict match
        rule_url = [
            {
                "key": "http.url",
                "values": ["http://example.com/health"],
                "match_type": "strict",
            }
        ]
        assert matches_rule(rule_url, span_attrs)

        # Contains match
        rule_contains = [
            {"key": "http.url", "values": ["health"], "match_type": "contains"}
        ]
        assert matches_rule(rule_contains, span_attrs)

    def test_matches_rule_multiple_rules(self) -> None:
        # matches_rule iterates over rule_attributes (list of rules).
        # Inside loop: if not rule_matched: return False (AND logic).
        # So all rules must match.

        span_attrs = {"type": "http", "http.url": "http://example.com/health"}

        rules = [
            {"key": "type", "values": ["http"]},
            {
                "key": "http.url",
                "values": ["http://example.com/health"],
                "match_type": "strict",
            },
        ]
        assert matches_rule(rules, span_attrs)

        rules_fail = [
            {"key": "type", "values": ["http"]},
            {
                "key": "http.url",
                "values": ["http://example.com/login"],
                "match_type": "strict",
            },
        ]
        assert not matches_rule(rules_fail, span_attrs)

    def test_match_key_filter_with_none_value(self) -> None:
        """Test that match_key_filter handles None span_value gracefully."""
        # None span_value should return False for all match types
        assert not match_key_filter(None, "foo", "strict")
        assert not match_key_filter(None, "foo", "contains")
        assert not match_key_filter(None, "foo", "startswith")
        assert not match_key_filter(None, "foo", "endswith")
        assert not match_key_filter(None, "*", "strict")

    def test_matches_rule_with_none_type_in_category(self) -> None:
        """Test that matches_rule handles None type when checking category."""
        # When type is None, category check should not match
        span_attrs_none_type = {"type": None}
        rule_category = [{"key": "category", "values": ["databases"]}]
        assert not matches_rule(rule_category, span_attrs_none_type)

        # When type is missing, category check should not match
        span_attrs_no_type = {}
        assert not matches_rule(rule_category, span_attrs_no_type)

    def test_matches_rule_with_none_attribute_value(self) -> None:
        """Test that matches_rule handles None attribute values gracefully."""
        # When an attribute value is None, it should not match
        span_attrs = {"http.url": None, "http.method": "GET"}

        rule_url = [
            {"key": "http.url", "values": ["example.com"], "match_type": "contains"}
        ]
        assert not matches_rule(rule_url, span_attrs)

        # But other attributes should still match
        rule_method = [
            {"key": "http.method", "values": ["GET"], "match_type": "strict"}
        ]
        assert matches_rule(rule_method, span_attrs)

    def test_resolve_nested_key_embedded_dot_keys(self) -> None:
        """Resolves sdk.custom.tags.http.host through a defaultdict structure —
        the exact layout produced by real SDK spans."""
        sdk_custom = defaultdict(dict)
        sdk_custom["tags"] = defaultdict(str)
        sdk_custom["tags"]["http.host"] = "agent.com.instana.io"

        assert (
            resolve_nested_key(
                {"sdk.custom": sdk_custom}, ["sdk", "custom", "tags", "http", "host"]
            )
            == "agent.com.instana.io"
        )

    def test_resolve_nested_key_returns_none_when_missing(self) -> None:
        """Returns None when the dotted path does not exist in the data."""
        assert (
            resolve_nested_key(
                {"sdk.custom": {"tags": {}}}, ["sdk", "custom", "tags", "http", "host"]
            )
            is None
        )

    def test_resolve_nested_key_with_empty_key_parts(self) -> None:
        """Returns None when key_parts is an empty list."""
        data = {"sdk.custom": {"tags": {"http.host": "example.com"}}}
        assert resolve_nested_key(data, []) is None

    def test_resolve_nested_key_with_non_dict_data(self) -> None:
        """Returns None when data is not a dictionary."""
        # Test with string
        assert resolve_nested_key("not a dict", ["key"]) is None

        # Test with list
        assert resolve_nested_key(["not", "a", "dict"], ["key"]) is None

        # Test with None
        assert resolve_nested_key(None, ["key"]) is None

        # Test with integer
        assert resolve_nested_key(42, ["key"]) is None

    def test_matches_rule_sdk_span_host_match(self) -> None:
        """SDK span whose sdk.custom.tags.http.host contains 'com.instana' should be filtered."""
        sdk_custom = defaultdict(dict)
        sdk_custom["tags"] = {"http.host": "agent.com.instana.io"}
        span_attrs = {
            "type": "sdk",
            "kind": 3,
            "sdk.name": "my-span",
            "sdk.custom": sdk_custom,
        }

        rule = [
            {
                "key": "sdk.custom.tags.http.host",
                "values": ["com.instana"],
                "match_type": "contains",
            }
        ]
        assert matches_rule(rule, span_attrs)

    def test_matches_rule_sdk_span_host_no_match(self) -> None:
        """SDK span with an unrelated host should NOT be filtered."""
        sdk_custom = defaultdict(dict)
        sdk_custom["tags"] = {"http.host": "myapp.example.com"}
        span_attrs = {
            "type": "sdk",
            "kind": 3,
            "sdk.name": "my-span",
            "sdk.custom": sdk_custom,
        }

        rule = [
            {
                "key": "sdk.custom.tags.http.host",
                "values": ["com.instana"],
                "match_type": "contains",
            }
        ]
        assert not matches_rule(rule, span_attrs)

    def test_matches_rule_sdk_span_url_match(self) -> None:
        """SDK span whose sdk.custom.tags.http.url contains 'com.instana' should be filtered.

        Covers the span shape:
          data.sdk.custom.tags.http.url = 'http://localhost:42699/com.instana.plugin.python.89262'
        """
        sdk_custom = defaultdict(dict)
        sdk_custom["tags"] = {
            "http.url": "http://localhost:42699/com.instana.plugin.python.89262"
        }
        span_attrs = {
            "type": "sdk",
            "kind": 3,
            "sdk.name": "HEAD",
            "sdk.custom": sdk_custom,
        }

        rule = [
            {
                "key": "sdk.custom.tags.http.url",
                "values": ["com.instana"],
                "match_type": "contains",
            }
        ]
        assert matches_rule(rule, span_attrs)
