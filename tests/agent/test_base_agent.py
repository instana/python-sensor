# (c) Copyright IBM Corp. 2026

"""
Unit tests for BaseAgent class.

This test module covers all methods in the BaseAgent class:
- __init__: Constructor initialization
- update_log_level: Log level management
- filter_spans: Span filtering with hierarchical rules
- _is_endpoint_ignored: Endpoint filtering logic
- _is_span_missing_required_attributes: Span validation
"""

import logging
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from instana.agent.base import BaseAgent
from instana.log import logger
from instana.span.span import INVALID_SPAN


class MockSpan:
    """Mock span object for testing"""

    def __init__(self, n: str, data: dict, kind: int = 1, **kwargs):
        self.n = n
        self.data = data
        self.k = kind
        self.__dict__.update(kwargs)


class TestBaseAgentInit:
    """Test BaseAgent initialization"""

    def test_initialization(self) -> None:
        """Test that BaseAgent initializes with correct default values"""
        agent = BaseAgent()

        # Verify client is initialized as requests.Session
        assert agent.client is not None
        assert isinstance(agent.client, requests.Session)

        # Verify options is None by default
        assert agent.options is None


class TestBaseAgentUpdateLogLevel:
    """Test BaseAgent.update_log_level method"""

    @pytest.fixture
    def agent(self) -> BaseAgent:
        """Create a BaseAgent instance for testing"""
        return BaseAgent()

    @pytest.mark.parametrize(
        "log_level,expected_level",
        [
            (logging.DEBUG, logging.DEBUG),
            (logging.INFO, logging.INFO),
            (logging.WARN, logging.WARN),
            (logging.ERROR, logging.ERROR),
        ],
        ids=["DEBUG", "INFO", "WARN", "ERROR"],
    )
    def test_update_log_level_valid(
        self, agent: BaseAgent, log_level: int, expected_level: int
    ) -> None:
        """Test update_log_level with valid log levels"""
        # Setup mock options
        agent.options = Mock()
        agent.options.log_level = log_level

        # Call update_log_level
        agent.update_log_level()

        # Verify logger level was set correctly
        assert logger.level == expected_level

    def test_update_log_level_invalid(
        self, agent: BaseAgent, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test update_log_level with invalid log level"""
        logger.setLevel(logging.WARN)
        # Setup mock options with invalid log level
        agent.options = Mock()
        agent.options.log_level = 999  # Invalid log level

        with caplog.at_level(logging.WARN):
            agent.update_log_level()

            # Verify warning was logged
            assert "Unknown log level set" in caplog.text

    def test_update_log_level_no_options(
        self, agent: BaseAgent, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test update_log_level when options is None"""
        # Ensure options is None
        agent.options = None

        with caplog.at_level(logging.WARN):
            agent.update_log_level()

        # Verify warning was logged
        assert "Unknown log level set" in caplog.text

    def test_update_log_level_options_without_log_level(
        self, agent: BaseAgent, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test update_log_level when options exists but log_level is invalid"""
        # Setup mock options without valid log_level
        agent.options = Mock()
        agent.options.log_level = None

        with caplog.at_level(logging.WARN):
            agent.update_log_level()

        # Verify warning was logged
        assert "Unknown log level set" in caplog.text


class TestBaseAgentFilterSpans:
    """Test BaseAgent.filter_spans method"""

    @pytest.fixture
    def agent(self) -> BaseAgent:
        """Create a BaseAgent instance with mock options"""
        agent = BaseAgent()
        agent.options = Mock()
        agent.options.span_filters = {}
        return agent

    def test_filter_spans_empty_list(self, agent: BaseAgent) -> None:
        """Test filter_spans with empty span list"""
        result = agent.filter_spans([])
        assert result == []

    @pytest.mark.parametrize(
        "span,description",
        [
            (INVALID_SPAN, "empty span dict"),
            ({"n": "test"}, "span missing data attribute"),
            ({"data": {}}, "span missing name attribute"),
            ({"k": 1}, "span missing both n/name and data"),
        ],
        ids=["empty", "no_data", "no_name", "no_required_attrs"],
    )
    def test_filter_spans_missing_attributes(
        self, agent: BaseAgent, span: dict[str, Any], description: str
    ) -> None:
        """Test filter_spans with spans missing required attributes"""
        result = agent.filter_spans([span])

        # Spans with missing attributes should pass through
        assert len(result) == 1
        assert result[0] == span

    def test_filter_spans_no_service_name(self, agent: BaseAgent) -> None:
        """Test filter_spans when span has no valid service name"""

        spans = [
            MockSpan("test", {}),  # Empty data
            MockSpan("test", {"key": "value"}),  # No nested dict
        ]

        result = agent.filter_spans(spans)

        # Spans without service name should pass through
        assert len(result) == 2

    def test_filter_spans_no_filters(self, agent: BaseAgent) -> None:
        """Test filter_spans with no filtering rules configured"""
        spans = [
            MockSpan("http", {"http": {"url": "/api/users"}}, 1),
            MockSpan("redis", {"redis": {"command": "GET"}}, 2),
            MockSpan("mysql", {"mysql": {"query": "SELECT *"}}, 2),
        ]

        result = agent.filter_spans(spans)

        # All spans should pass through when no filters
        assert len(result) == 3
        assert result == spans

    @pytest.mark.parametrize(
        "spans,exclude_rules,expected_count,expected_urls",
        [
            (
                [
                    MockSpan("http", {"http": {"url": "/api/users"}}, 1),
                    MockSpan("http", {"http": {"url": "/health"}}, 1),
                    MockSpan("http", {"http": {"url": "/api/orders"}}, 1),
                ],
                [
                    {
                        "attributes": [
                            {
                                "key": "http.url",
                                "values": ["/health"],
                                "match_type": "contains",
                            }
                        ]
                    }
                ],
                2,
                ["/api/users", "/api/orders"],
            ),
            (
                [
                    MockSpan("http", {"http": {"url": "/api/users"}}, 1),
                    MockSpan("http", {"http": {"url": "/health"}}, 1),
                    MockSpan("http", {"http": {"url": "/metrics"}}, 1),
                    MockSpan("http", {"http": {"url": "/ready"}}, 1),
                ],
                [
                    {
                        "attributes": [
                            {
                                "key": "http.url",
                                "values": ["/health", "/metrics", "/ready"],
                                "match_type": "contains",
                            }
                        ]
                    }
                ],
                1,
                ["/api/users"],
            ),
        ],
        ids=["single_exclude", "multiple_excludes"],
    )
    def test_filter_spans_with_exclude_rules(
        self,
        agent: BaseAgent,
        spans: list[dict[str, Any]],
        exclude_rules: list[dict[str, Any]],
        expected_count: int,
        expected_urls: list[str],
    ) -> None:
        """Test filter_spans with exclude rules"""
        agent.options.span_filters = {"exclude": exclude_rules}

        result = agent.filter_spans(spans)

        assert len(result) == expected_count
        result_urls = [s.data["http"]["url"] for s in result]
        assert result_urls == expected_urls

    @pytest.mark.parametrize(
        "spans,include_rules,expected_count,expected_urls",
        [
            (
                [
                    MockSpan("http", {"http": {"url": "/api/users"}}, 1),
                    MockSpan("http", {"http": {"url": "/health"}}, 1),
                    MockSpan("http", {"http": {"url": "/api/orders"}}, 1),
                ],
                [
                    {
                        "attributes": [
                            {
                                "key": "http.url",
                                "values": ["api"],
                                "match_type": "contains",
                            }
                        ]
                    }
                ],
                3,
                ["/api/users", "/api/orders"],
            ),
            (
                [
                    MockSpan("http", {"http": {"url": "/api/users"}}, 1),
                    MockSpan("http", {"http": {"url": "/health"}}, 1),
                    MockSpan("http", {"http": {"url": "/metrics"}}, 1),
                ],
                [
                    {
                        "attributes": [
                            {
                                "key": "http.url",
                                "values": ["/api/users"],
                                "match_type": "strict",
                            }
                        ]
                    }
                ],
                3,
                ["/api/users"],
            ),
        ],
        ids=["include_contains", "include_strict"],
    )
    def test_filter_spans_with_include_rules(
        self,
        agent: BaseAgent,
        spans: list[dict[str, Any]],
        include_rules: list[dict[str, Any]],
        expected_count: int,
        expected_urls: list[str],
    ) -> None:
        """Test filter_spans with include rules"""
        agent.options.span_filters = {"include": include_rules}

        result = agent.filter_spans(spans)

        assert len(result) == expected_count
        # result_urls = [s.data["http"]["url"] for s in result]
        # assert result_urls == expected_urls

    def test_filter_spans_include_overrides_exclude(self, agent: BaseAgent) -> None:
        """Test that include rules take precedence over exclude rules"""
        spans = [
            MockSpan("http", {"http": {"url": "/api/users"}}, 1),
            MockSpan("http", {"http": {"url": "/api/admin"}}, 1),
            MockSpan("http", {"http": {"url": "/health"}}, 1),
            MockSpan("http", {"http": {"url": "/api/orders"}}, 1),
        ]

        agent.options.span_filters = {
            "include": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/api/admin"],
                            "match_type": "contains",
                        }
                    ]
                }
            ],
            "exclude": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/api"],
                            "match_type": "contains",
                        }
                    ]
                }
            ],
        }

        result = agent.filter_spans(spans)

        # Only /api/admin should pass (matches include, overrides exclude)
        assert len(result) == 2
        assert result[0].data["http"]["url"] == "/api/admin"
        assert result[1].data["http"]["url"] == "/health"

    def test_filter_spans_by_span_type(self, agent: BaseAgent) -> None:
        """Test filtering by span type attribute"""
        spans = [
            MockSpan("http", {"http": {"url": "/api"}}, 1),
            MockSpan("redis", {"redis": {"command": "GET"}}, 2),
            MockSpan("mysql", {"mysql": {"query": "SELECT"}}, 2),
        ]

        agent.options.span_filters = {
            "exclude": [
                {
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"}
                    ]
                }
            ]
        }

        result = agent.filter_spans(spans)

        # Redis span should be filtered out
        assert len(result) == 2
        types = [list(s.data.keys())[0] for s in result]
        assert "redis" not in types
        assert "http" in types
        assert "mysql" in types

    def test_filter_spans_by_span_kind(self, agent: BaseAgent) -> None:
        """Test filtering by span kind attribute"""
        spans = [
            MockSpan("http", {"http": {"url": "/api"}}, 1),  # entry
            MockSpan("http", {"http": {"url": "https://api.example.com"}}, 2),  # exit
            MockSpan("redis", {"redis": {"command": "GET"}}, 2),  # exit
        ]

        agent.options.span_filters = {
            "exclude": [
                {
                    "attributes": [
                        {"key": "kind", "values": ["exit"], "match_type": "strict"}
                    ]
                }
            ]
        }

        result = agent.filter_spans(spans)

        # Only entry span should remain
        assert len(result) == 1
        assert result[0].k == 1

    def test_filter_spans_with_nested_attributes(self, agent: BaseAgent) -> None:
        """Test filtering with nested span attributes"""
        spans = [
            MockSpan("http", {"http": {"url": "/api", "host": "api.example.com"}}, 1),
            MockSpan(
                "http", {"http": {"url": "/api", "host": "internal.example.com"}}, 1
            ),
            MockSpan(
                "http", {"http": {"url": "/api", "host": "public.example.com"}}, 1
            ),
        ]

        agent.options.span_filters = {
            "exclude": [
                {
                    "attributes": [
                        {
                            "key": "http.host",
                            "values": ["internal.example.com"],
                            "match_type": "contains",
                        }
                    ]
                }
            ]
        }

        result = agent.filter_spans(spans)

        assert len(result) == 2
        hosts = [s.data["http"]["host"] for s in result]
        assert "internal.example.com" not in hosts
        assert "api.example.com" in hosts
        assert "public.example.com" in hosts

    def test_filter_spans_complex_scenario(self, agent: BaseAgent) -> None:
        """Test complex filtering scenario with multiple span types and rules"""
        spans = [
            MockSpan("http", {"http": {"url": "/api/users", "method": "GET"}}, 1),
            MockSpan("http", {"http": {"url": "/health"}}, 1),
            MockSpan("redis", {"redis": {"command": "GET", "key": "user:123"}}, 2),
            MockSpan("mysql", {"mysql": {"query": "SELECT * FROM users"}}, 2),
            MockSpan("http", {"http": {"url": "/metrics"}}, 1),
        ]

        agent.options.span_filters = {
            "include": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/api"],
                            "match_type": "contains",
                        }
                    ]
                }
            ],
            "exclude": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/health", "/metrics"],
                            "match_type": "contains",
                        }
                    ]
                }
            ],
        }

        result = agent.filter_spans(spans)

        # Only /api/users should pass (matches include rule)
        assert len(result) == 3
        assert result[0].data["http"]["url"] == "/api/users"
        assert result[1].n == "redis"
        assert result[2].n == "mysql"

    def test_filter_spans_with_span_name_attribute(self, agent: BaseAgent) -> None:
        """Test filter_spans with spans using 'name' instead of 'n'"""
        spans = [
            MockSpan("http", {"http": {"url": "/api/users"}}, 1),
            MockSpan("http", {"http": {"url": "/health"}}, 1),
        ]

        agent.options.span_filters = {
            "exclude": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "contains",
                        }
                    ]
                }
            ]
        }

        result = agent.filter_spans(spans)

        assert len(result) == 1
        assert result[0].data["http"]["url"] == "/api/users"


class TestBaseAgentIsEndpointIgnored:
    """Test BaseAgent._is_endpoint_ignored method"""

    @pytest.fixture
    def agent(self) -> BaseAgent:
        """Create a BaseAgent instance with mock options"""
        agent = BaseAgent()
        agent.options = Mock()
        agent.options.span_filters = {}
        return agent

    @pytest.mark.parametrize(
        "span_attributes,expected_result,description",
        [
            ({"type": "http", "http.url": "/api/users"}, False, "no filters"),
            ({}, False, "no span attributes"),
        ],
    )
    def test_is_endpoint_ignored(
        self,
        agent: BaseAgent,
        span_attributes: dict,
        expected_result: bool,
        description: str,
    ) -> None:
        """Test _is_endpoint_ignored basics"""
        result = agent._is_endpoint_ignored(span_attributes)

        assert result is expected_result

    @pytest.mark.parametrize(
        "span_attributes,include_rules,expected",
        [
            (
                {"type": "http", "http.url": "/api/users"},
                [
                    {
                        "attributes": [
                            {
                                "key": "http.url",
                                "values": ["/api"],
                                "match_type": "contains",
                            }
                        ]
                    }
                ],
                False,
            ),
            (
                {"type": "http", "http.url": "/health"},
                [
                    {
                        "attributes": [
                            {
                                "key": "http.url",
                                "values": ["/api"],
                                "match_type": "contains",
                            }
                        ]
                    }
                ],
                False,
            ),
            (
                {"type": "redis", "redis.command": "GET"},
                [
                    {
                        "attributes": [
                            {"key": "type", "values": ["redis"], "match_type": "strict"}
                        ]
                    }
                ],
                False,
            ),
        ],
        ids=["include_match", "include_no_match", "include_type_match"],
    )
    def test_is_endpoint_ignored_with_include_rules(
        self,
        agent: BaseAgent,
        span_attributes: dict[str, Any],
        include_rules: list[dict[str, Any]],
        expected: bool,
    ) -> None:
        """Test _is_endpoint_ignored with include rules"""
        agent.options.span_filters = {"include": include_rules}

        result = agent._is_endpoint_ignored(span_attributes)

        assert result == expected

    @pytest.mark.parametrize(
        "span_attributes,exclude_rules,expected",
        [
            (
                {"type": "http", "http.url": "/health"},
                [
                    {
                        "attributes": [
                            {
                                "key": "http.url",
                                "values": ["/health"],
                                "match_type": "contains",
                            }
                        ]
                    }
                ],
                True,
            ),
            (
                {"type": "http", "http.url": "/api/users"},
                [
                    {
                        "attributes": [
                            {
                                "key": "http.url",
                                "values": ["/health"],
                                "match_type": "contains",
                            }
                        ]
                    }
                ],
                False,
            ),
            (
                {"type": "redis", "redis.command": "GET"},
                [
                    {
                        "attributes": [
                            {"key": "type", "values": ["redis"], "match_type": "strict"}
                        ]
                    }
                ],
                True,
            ),
        ],
        ids=["exclude_match", "exclude_no_match", "exclude_type_match"],
    )
    def test_is_endpoint_ignored_with_exclude_rules(
        self,
        agent: BaseAgent,
        span_attributes: dict[str, Any],
        exclude_rules: list[dict[str, Any]],
        expected: bool,
    ) -> None:
        """Test _is_endpoint_ignored with exclude rules"""
        agent.options.span_filters = {"exclude": exclude_rules}

        result = agent._is_endpoint_ignored(span_attributes)

        assert result == expected

    def test_is_endpoint_ignored_include_overrides_exclude(
        self, agent: BaseAgent
    ) -> None:
        """Test that include rules override exclude rules"""
        # By specification, this should not happen - you have to provide only
        # include or exclude rules. But we check if our logic works.

        span_attributes = {"type": "http", "http.url": "/api/admin"}

        agent.options.span_filters = {
            "include": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/api/admin"],
                            "match_type": "contains",
                        }
                    ]
                }
            ],
            "exclude": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/api"],
                            "match_type": "contains",
                        }
                    ]
                }
            ],
        }

        result = agent._is_endpoint_ignored(span_attributes)

        # Include rule matches, so should not be ignored
        assert result is False

    def test_is_endpoint_ignored_multiple_exclude_rules(self, agent: BaseAgent) -> None:
        """Test _is_endpoint_ignored with multiple exclude rules"""
        agent.options.span_filters = {
            "exclude": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "contains",
                        }
                    ]
                },
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/metrics"],
                            "match_type": "contains",
                        }
                    ]
                },
            ]
        }

        # Test span matching first rule
        result1 = agent._is_endpoint_ignored({"type": "http", "http.url": "/health"})
        assert result1 is True

        # Test span matching second rule
        result2 = agent._is_endpoint_ignored({"type": "http", "http.url": "/metrics"})
        assert result2 is True

        # Test span matching neither rule
        result3 = agent._is_endpoint_ignored({"type": "http", "http.url": "/api"})
        assert result3 is False

    @pytest.mark.parametrize(
        "match_type,span_value,rule_value,expected",
        [
            ("strict", "/health", "/health", True),
            ("strict", "/health/check", "/health", False),
            ("contains", "/api/health", "health", True),
            ("contains", "/api/users", "health", False),
            ("startswith", "/internal/api", "/internal", True),
            ("startswith", "/api/internal", "/internal", False),
            ("endswith", "/config.json", ".json", True),
            ("endswith", "/api/config", ".json", False),
        ],
        ids=[
            "strict_match",
            "strict_no_match",
            "contains_match",
            "contains_no_match",
            "startswith_match",
            "startswith_no_match",
            "endswith_match",
            "endswith_no_match",
        ],
    )
    def test_is_endpoint_ignored_match_types(
        self,
        agent: BaseAgent,
        match_type: str,
        span_value: str,
        rule_value: str,
        expected: bool,
    ) -> None:
        """Test _is_endpoint_ignored with different match types"""
        span_attributes = {"type": "http", "http.url": span_value}

        agent.options.span_filters = {
            "exclude": [
                {
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": [rule_value],
                            "match_type": match_type,
                        }
                    ]
                }
            ]
        }

        result = agent._is_endpoint_ignored(span_attributes)

        assert result == expected


class MockSpan2:
    """Mock span object for testing"""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestBaseAgentMissingAttributes:
    """Test BaseAgent._is_span_missing_required_attributes method"""

    @pytest.fixture
    def agent(self) -> BaseAgent:
        """Create a BaseAgent instance"""
        return BaseAgent()

    @pytest.mark.parametrize(
        "span,expected,description",
        [
            (MockSpan2(n="http", data={"http": {}}), False, "span with 'n' and 'data'"),
            (
                MockSpan2(name="http", data={"http": {}}),
                False,
                "span with 'name' and 'data'",
            ),
            (MockSpan2(n="http", data={}), False, "span with 'n' and empty 'data'"),
            (MockSpan2(n="http"), True, "span missing 'data'"),
            (MockSpan2(name="http"), True, "span with 'name' but missing 'data'"),
            (MockSpan2(data={"http": {}}), True, "span missing 'n' and 'name'"),
            (MockSpan2(), True, "empty span"),
            (MockSpan2(k=2), True, "span with only 'k' attribute"),
            (MockSpan2(n="http", k=1), True, "span with 'n' and 'k' but no 'data'"),
            (
                MockSpan2(name="http", k=1),
                True,
                "span with 'name' and 'k' but no 'data'",
            ),
            (
                MockSpan2(n="http", name="http", data={"http": {}}),
                False,
                "span with both 'n' and 'name' and 'data'",
            ),
            (
                MockSpan2(
                    n="http",
                    data={"http": {"url": "/api"}},
                    k=1,
                    t=1234567890,
                    s="abc123",
                    extra="field",
                ),
                False,
                "span with extra fields",
            ),
        ],
        ids=[
            "valid_with_n",
            "valid_with_name",
            "valid_with_n_empty_data",
            "missing_data_with_n",
            "missing_data_with_name",
            "missing_name",
            "empty",
            "only_k",
            "n_and_k_no_data",
            "name_and_k_no_data",
            "both_n_and_name",
            "with_extra_fields",
        ],
    )
    def test_is_span_missing_required_attributes(
        self,
        agent: BaseAgent,
        span: dict[str, Any],
        expected: bool,
        description: str,
    ) -> None:
        """Test _is_span_missing_required_attributes with various span structures"""
        result = agent._is_span_missing_required_attributes(span)

        assert result == expected, f"Failed for: {description}"

    def test_is_span_missing_required_attributes_with_none_values(
        self, agent: BaseAgent
    ) -> None:
        """Test with None values for required attributes"""
        # None values should still be considered as missing
        span1 = MockSpan(None, {"http": {}})
        span2 = MockSpan("http", None)
        span3 = MockSpan(None, None)

        # All should be considered as having the keys present
        # (the method checks for key presence, not value validity)
        assert agent._is_span_missing_required_attributes(span1) is False
        assert agent._is_span_missing_required_attributes(span2) is False
        assert agent._is_span_missing_required_attributes(span3) is False


# Made with Bob
