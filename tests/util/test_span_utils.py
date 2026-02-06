# (c) Copyright IBM Corp. 2025

from instana.util.span_utils import matches_rule, match_key_filter, get_span_kind


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
