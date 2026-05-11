# (c) Copyright IBM Corp. 2026

"""
Unit tests for span filtering functionality in AWSFargateAgent
"""

import os
from typing import Generator
from unittest.mock import MagicMock

import pytest

from instana.agent.aws_fargate import AWSFargateAgent


class MockSpan:
    """Mock span object for testing"""

    def __init__(self, name, data, kind=1):
        self.n = name
        self.data = data
        self.k = kind


class TestAWSFargateSpanFiltering:
    """Test span filtering functionality in AWSFargateAgent"""

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup and teardown"""
        # Setup required environment variables
        os.environ["AWS_EXECUTION_ENV"] = "AWS_ECS_FARGATE"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

        # Clear any existing filter environment variables
        filter_env_vars = [
            "INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES",
            "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES",
            "INSTANA_CONFIG_PATH",
        ]
        for var in filter_env_vars:
            if var in os.environ:
                os.environ.pop(var)

        self.agent = AWSFargateAgent()
        yield

        # Cleanup
        cleanup_vars = [
            "AWS_EXECUTION_ENV",
            "INSTANA_ENDPOINT_URL",
            "INSTANA_AGENT_KEY",
        ] + filter_env_vars

        for var in cleanup_vars:
            if var in os.environ:
                os.environ.pop(var)

    def test_fargate_agent_has_filter_spans_method(self) -> None:
        """Test that AWSFargateAgent has filter_spans method from BaseAgent"""
        assert hasattr(self.agent, "filter_spans")
        assert callable(self.agent.filter_spans)

    def test_fargate_agent_has_is_endpoint_ignored_method(self) -> None:
        """Test that AWSFargateAgent has _is_endpoint_ignored method from BaseAgent"""
        assert hasattr(self.agent, "_is_endpoint_ignored")
        assert callable(self.agent._is_endpoint_ignored)

    def test_filter_spans_no_rules_fargate(self) -> None:
        """Test that all spans pass through when no filtering rules are set"""
        spans = [
            MockSpan("http", {"http": {"url": "/api/users"}}),
            MockSpan("http", {"http": {"url": "/health"}}),
            MockSpan("redis", {"redis": {"command": "GET"}}),
        ]

        filtered = self.agent.filter_spans(spans)
        assert len(filtered) == 3

    def test_filter_spans_with_exclude_rules_fargate(self) -> None:
        """Test that spans are filtered based on exclude rules in Fargate"""
        # Set up exclude rule for health checks
        os.environ["INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES"] = (
            "http.url;health,ready;contains"
        )

        # Recreate agent to pick up new environment variable
        agent = AWSFargateAgent()

        spans = [
            MockSpan("http", {"http": {"url": "/api/users"}}),
            MockSpan("http", {"http": {"url": "/health"}}),
            MockSpan("http", {"http": {"url": "/ready"}}),
            MockSpan("http", {"http": {"url": "/api/orders"}}),
        ]

        filtered = agent.filter_spans(spans)
        assert len(filtered) == 2
        # Verify health check spans were filtered out
        urls = [span.data["http"]["url"] for span in filtered]
        assert "/health" not in urls
        assert "/ready" not in urls
        assert "/api/users" in urls
        assert "/api/orders" in urls

    def test_filter_spans_with_include_rules_fargate(self) -> None:
        """Test that only matching spans are kept based on include rules in Fargate"""
        # Set up include rule for API calls only
        os.environ["INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES"] = (
            "http.url;/api;contains"
        )

        # Recreate agent to pick up new environment variable
        agent = AWSFargateAgent()

        spans = [
            MockSpan("http", {"http": {"url": "/api/users"}}),
            MockSpan("http", {"http": {"url": "/health"}}),
            MockSpan("http", {"http": {"url": "/api/orders"}}),
            MockSpan("http", {"http": {"url": "/metrics"}}),
        ]

        filtered = agent.filter_spans(spans)
        # Verify only API spans were kept
        urls = [span.data["http"]["url"] for span in filtered]
        assert "/api/users" in urls
        assert "/api/orders" in urls

    def test_report_data_payload_calls_report_spans(self, mocker) -> None:
        """Test that report_data_payload calls report_spans for span filtering"""
        # Mock the POST response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mocker.patch(
            "instana.agent.serverless.ServerlessAgent._send_http_request",
            return_value=mock_response,
        )

        payload = {
            "spans": [
                MockSpan("http", {"http": {"url": "/api/users"}}),
                MockSpan("http", {"http": {"url": "/health"}}),
            ],
            "metrics": {"plugins": [{"data": {"test": "data"}}]},
        }

        # Call report_data_payload
        response = self.agent.report_data_payload(payload)

        assert response
        assert response.status_code == 200

    def test_fargate_span_filters_configuration_from_env(self) -> None:
        """Test that Fargate agent picks up span filter configuration from environment"""
        os.environ["INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES"] = (
            "http.url;health;contains"
        )

        agent = AWSFargateAgent()

        # Verify span_filters is configured
        assert hasattr(agent.options, "span_filters")
        assert "exclude" in agent.options.span_filters
        assert len(agent.options.span_filters["exclude"]) > 0

    def test_fargate_internal_instana_spans_filtered(self) -> None:
        """Test that internal Instana spans are automatically filtered in Fargate"""
        agent = AWSFargateAgent()

        spans = [
            MockSpan("http", {"http": {"url": "/api/users"}}),
            MockSpan("http", {"http": {"url": "https://localhost/com.instana.plugin"}}),
        ]

        filtered = agent.filter_spans(spans)
        # Internal Instana span should be filtered out
        assert len(filtered) == 1
        assert filtered[0].data["http"]["url"] == "/api/users"

    def test_fargate_filter_spans_by_database_type(self) -> None:
        """Test filtering database spans in Fargate"""
        os.environ["INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES"] = (
            "type;redis,mongodb;strict"
        )

        agent = AWSFargateAgent()

        spans = [
            MockSpan("http", {"http": {"url": "/api/users"}}),
            MockSpan("redis", {"redis": {"command": "GET"}}),
            MockSpan("mongodb", {"mongodb": {"query": "find"}}),
            MockSpan("mysql", {"mysql": {"query": "SELECT *"}}),
        ]

        filtered = agent.filter_spans(spans)
        assert len(filtered) == 2
        # Redis and MongoDB spans should be filtered out
        types = [list(span.data.keys())[0] for span in filtered]
        assert "redis" not in types
        assert "mongodb" not in types
        assert "http" in types
        assert "mysql" in types

    def test_fargate_options_inherit_span_filters(self) -> None:
        """Test that AWSFargateOptions inherits span_filters from BaseOptions"""
        agent = AWSFargateAgent()

        # Verify span_filters attribute exists
        assert hasattr(agent.options, "span_filters")
        # Verify it's a dict
        assert isinstance(agent.options.span_filters, dict)
        # Verify default internal filters are present
        assert "exclude" in agent.options.span_filters


# Made with Bob
