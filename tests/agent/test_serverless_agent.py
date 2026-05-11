# (c) Copyright IBM Corp. 2026

"""
Unit tests for ServerlessAgent base class.

Tests common functionality shared by all serverless agents including:
- Initialization workflow
- Span filtering
- Header building
- Payload preparation
- HTTP request handling
- Template method pattern
"""

import logging
import os
from typing import Generator
from unittest.mock import MagicMock, Mock, patch

import pytest
from requests import Response

from instana.agent.serverless import ServerlessAgent
from instana.options import AWSFargateOptions


class MockSpan:
    """Mock span object for testing"""

    def __init__(self, n: str, data: dict, kind: int = 1, **kwargs):
        self.n = n
        self.data = data
        self.k = kind
        self.__dict__.update(kwargs)


class ConcreteServerlessAgent(ServerlessAgent):
    """Concrete implementation of ServerlessAgent for testing."""

    def _initialize_platform(self) -> None:
        """Initialize with test options."""
        self.options = AWSFargateOptions()

    def _create_collector(self):
        """Create mock collector."""
        mock_collector = Mock()
        mock_collector.get_fq_arn = Mock(return_value="test-entity-123")
        mock_collector.start = Mock()
        return mock_collector

    def _get_entity_id(self) -> str:
        """Return test entity ID."""
        return "test-entity-123"

    def _get_cloud_provider(self) -> str:
        """Return test cloud provider."""
        return "test"

    def _get_platform_name(self) -> str:
        """Return test platform name."""
        return "Test Platform"


class TestServerlessAgent:
    """Test suite for ServerlessAgent base class."""

    @pytest.fixture(autouse=True)
    def _resource(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> Generator[None, None, None]:
        """Setup and teardown for each test."""
        # Setup
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "test_key_123"

        yield
        # Teardown
        caplog.clear()
        env_vars = [
            "INSTANA_ENDPOINT_URL",
            "INSTANA_AGENT_KEY",
        ]
        for var in env_vars:
            if var in os.environ:
                os.environ.pop(var)

    def test_initialization_success(self) -> None:
        """Test that agent initializes correctly with valid options."""
        agent = ConcreteServerlessAgent()

        assert agent
        assert agent.collector
        assert agent.report_headers is None  # Lazy initialization
        assert agent._can_send is True
        assert hasattr(agent, "options")
        assert agent.options.endpoint_url == "https://localhost/notreal"
        assert agent.options.agent_key == "test_key_123"

    def test_initialization_failure_missing_endpoint(self) -> None:
        """Test that agent handles missing endpoint URL gracefully."""
        os.environ.pop("INSTANA_ENDPOINT_URL")

        agent = ConcreteServerlessAgent()

        assert agent._can_send is False
        assert agent.collector is None

    def test_initialization_failure_missing_key(self) -> None:
        """Test that agent handles missing agent key gracefully."""
        os.environ.pop("INSTANA_AGENT_KEY")

        agent = ConcreteServerlessAgent()

        assert agent._can_send is False
        assert agent.collector is None

    def test_can_send_returns_true_when_valid(self) -> None:
        """Test can_send returns True when agent is properly configured."""
        agent = ConcreteServerlessAgent()

        assert agent.can_send() is True

    def test_can_send_returns_false_when_invalid(self) -> None:
        """Test can_send returns False when agent is not configured."""
        os.environ.pop("INSTANA_AGENT_KEY")
        agent = ConcreteServerlessAgent()

        assert agent.can_send() is False

    def test_get_from_structure(self) -> None:
        """Test that from structure is built correctly."""
        agent = ConcreteServerlessAgent()

        from_structure = agent.get_from_structure()

        assert from_structure == {"hl": True, "cp": "test", "e": "test-entity-123"}

    def test_validate_options_with_valid_config(self) -> None:
        """Test options validation with valid configuration."""
        agent = ConcreteServerlessAgent()

        assert agent._validate_options() is True

    def test_validate_options_with_missing_endpoint(self) -> None:
        """Test options validation with missing endpoint."""
        os.environ.pop("INSTANA_ENDPOINT_URL")
        agent = ConcreteServerlessAgent()

        assert agent._validate_options() is False

    def test_validate_options_with_missing_key(self) -> None:
        """Test options validation with missing key."""
        os.environ.pop("INSTANA_AGENT_KEY")
        agent = ConcreteServerlessAgent()

        assert agent._validate_options() is False

    def test_prepare_payload_filters_spans(self) -> None:
        """Test that _prepare_payload filters spans correctly."""
        agent = ConcreteServerlessAgent()

        payload = {
            "spans": [
                MockSpan("http", {"http": {"url": "/api/users"}}),
                MockSpan("http", {"http": {"url": "/api/orders"}}),
            ],
            "metrics": {"test": "data"},
        }

        result = agent._prepare_payload(payload)

        assert "spans" in result
        assert len(result["spans"]) == 2
        assert "metrics" in result

    def test_prepare_payload_with_span_filtering_rules(self) -> None:
        """Test payload preparation with span filtering rules."""
        os.environ["INSTANA_TRACING_FILTER_EXCLUDE_HEALTH_ATTRIBUTES"] = (
            "http.url;health;contains"
        )
        agent = ConcreteServerlessAgent()

        payload = {
            "spans": [
                MockSpan("http", {"http": {"url": "/api/users"}}),
                MockSpan("http", {"http": {"url": "/health"}}),
                MockSpan("http", {"http": {"url": "/api/orders"}}),
            ]
        }

        result = agent._prepare_payload(payload)

        assert "spans" in result
        assert len(result["spans"]) == 2

    def test_prepare_payload_with_no_spans(self) -> None:
        """Test payload preparation when no spans are present."""
        agent = ConcreteServerlessAgent()

        payload = {"metrics": {"test": "data"}}

        result = agent._prepare_payload(payload)

        assert "metrics" in result
        assert "spans" not in result or len(result.get("spans", [])) == 0

    def test_build_headers(self) -> None:
        """Test that headers are built correctly."""
        agent = ConcreteServerlessAgent()

        headers = agent._build_headers()

        assert headers["Content-Type"] == "application/json"
        assert headers["X-Instana-Host"] == "test-entity-123"
        assert headers["X-Instana-Key"] == "test_key_123"

    def test_build_headers_lazy_initialization(self) -> None:
        """Test that headers are lazily initialized."""
        agent = ConcreteServerlessAgent()

        assert agent.report_headers is None

        # First call should initialize
        payload = {"spans": [], "metrics": {}}
        with patch.object(agent.client, "post") as mock_post:
            mock_post.return_value = Mock(status_code=200)
            agent.report_data_payload(payload)

        assert agent.report_headers is not None
        assert isinstance(agent.report_headers, dict)

    def test_get_endpoint_url(self) -> None:
        """Test endpoint URL construction."""
        agent = ConcreteServerlessAgent()

        url = agent._get_endpoint_url()

        assert url == "https://localhost/notreal/bundle"

    def test_get_instana_host_header_default(self) -> None:
        """Test default X-Instana-Host header value."""
        agent = ConcreteServerlessAgent()

        header_value = agent._get_instana_host_header()

        assert header_value == "test-entity-123"

    def test_get_custom_headers_default(self) -> None:
        """Test that default custom headers returns None."""
        agent = ConcreteServerlessAgent()

        custom_headers = agent._get_custom_headers()

        assert custom_headers is None

    @patch.object(ConcreteServerlessAgent, "_send_http_request")
    def test_report_data_payload_success(self, mock_send: MagicMock) -> None:
        """Test successful data payload reporting."""
        mock_response = Mock(spec=Response)
        mock_response.status_code = 200
        mock_send.return_value = mock_response

        agent = ConcreteServerlessAgent()
        payload = {
            "spans": [{"n": "http", "data": {"http": {"url": "/api/test"}}}],
            "metrics": {"test": "data"},
        }

        response = agent.report_data_payload(payload)

        assert response is not None
        assert response.status_code == 200
        mock_send.assert_called_once()

    @patch.object(ConcreteServerlessAgent, "_send_http_request")
    def test_report_data_payload_with_error_status(
        self, mock_send: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test data payload reporting with error status code."""
        agent = ConcreteServerlessAgent()

        caplog.set_level(logging.INFO, logger="instana")
        caplog.clear()

        mock_response = Mock(spec=Response)
        mock_response.status_code = 500
        mock_send.return_value = mock_response

        payload = {"spans": [], "metrics": {}}

        response = agent.report_data_payload(payload)

        assert response is not None
        assert response.status_code == 500
        assert any("status code 500" in msg for msg in caplog.messages)

    @patch.object(ConcreteServerlessAgent, "_send_http_request")
    def test_report_data_payload_with_exception(
        self, mock_send: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test data payload reporting handles exceptions."""
        agent = ConcreteServerlessAgent()

        caplog.set_level(logging.DEBUG, logger="instana")
        caplog.clear()

        mock_send.side_effect = Exception("Connection error")

        payload = {"spans": [], "metrics": {}}

        response = agent.report_data_payload(payload)

        assert response is None
        assert any("connection error" in msg.lower() for msg in caplog.messages)

    def test_validate_response_success(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test response validation with successful status."""
        caplog.set_level(logging.INFO, logger="instana")

        agent = ConcreteServerlessAgent()
        mock_response = Mock(spec=Response)
        mock_response.status_code = 200

        agent._validate_response(mock_response)

        # Should not log anything for successful response
        assert len(caplog.messages) == 0

    def test_validate_response_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test response validation with error status."""
        agent = ConcreteServerlessAgent()

        caplog.set_level(logging.INFO, logger="instana")
        caplog.clear()

        mock_response = Mock(spec=Response)
        mock_response.status_code = 404

        agent._validate_response(mock_response)

        assert len(caplog.messages) == 1
        assert "status code 404" in caplog.messages[0]

    def test_log_validation_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that validation failure is logged."""
        caplog.set_level(logging.WARNING, logger="instana")

        os.environ.pop("INSTANA_AGENT_KEY")
        agent = ConcreteServerlessAgent()

        assert agent
        assert any("INSTANA_AGENT_KEY" in msg for msg in caplog.messages)
        assert any("INSTANA_ENDPOINT_URL" in msg for msg in caplog.messages)
        assert any("Test Platform" in msg for msg in caplog.messages)

    def test_span_filtering_inheritance(self) -> None:
        """Test that span filtering is inherited from BaseAgent."""
        agent = ConcreteServerlessAgent()

        # Verify filter_spans method exists and is callable
        assert hasattr(agent, "filter_spans")
        assert callable(agent.filter_spans)

        # Test basic filtering
        spans = [{"n": "http", "data": {"http": {"url": "/api/test"}}}]
        filtered = agent.filter_spans(spans)

        assert isinstance(filtered, list)
        assert len(filtered) == 1

    def test_template_method_pattern(self) -> None:
        """Test that template method pattern is correctly implemented."""
        agent = ConcreteServerlessAgent()

        # Verify all abstract methods are implemented
        assert hasattr(agent, "_initialize_platform")
        assert hasattr(agent, "_create_collector")
        assert hasattr(agent, "_get_entity_id")
        assert hasattr(agent, "_get_cloud_provider")
        assert hasattr(agent, "_get_platform_name")

        # Verify template methods exist
        assert hasattr(agent, "report_data_payload")
        assert hasattr(agent, "_prepare_payload")
        assert hasattr(agent, "_build_headers")
        assert hasattr(agent, "_send_http_request")
        assert hasattr(agent, "_validate_response")

    @pytest.mark.parametrize(
        "status_code,should_log",
        [
            (200, False),
            (201, False),
            (204, False),
            (299, False),
            (300, True),
            (400, True),
            (404, True),
            (500, True),
        ],
    )
    def test_validate_response_status_codes(
        self, status_code: int, should_log: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test response validation with various status codes."""
        agent = ConcreteServerlessAgent()

        caplog.set_level(logging.INFO, logger="instana")
        caplog.clear()

        mock_response = Mock(spec=Response)
        mock_response.status_code = status_code

        agent._validate_response(mock_response)

        if should_log:
            assert len(caplog.messages) > 0
            assert str(status_code) in caplog.messages[0]
        else:
            assert len(caplog.messages) == 0

    def test_constants(self) -> None:
        """Test that class constants are defined correctly."""
        assert ServerlessAgent.CONTENT_TYPE == "application/json"
        assert ServerlessAgent.BUNDLE_ENDPOINT == "/bundle"

    def test_options_inheritance(self) -> None:
        """Test that options are properly inherited."""
        agent = ConcreteServerlessAgent()

        assert hasattr(agent.options, "endpoint_url")
        assert hasattr(agent.options, "agent_key")
        assert hasattr(agent.options, "timeout")
        assert hasattr(agent.options, "ssl_verify")
        assert hasattr(agent.options, "endpoint_proxy")
        assert hasattr(agent.options, "span_filters")

    def test_client_session_exists(self) -> None:
        """Test that HTTP client session is initialized."""
        agent = ConcreteServerlessAgent()

        assert hasattr(agent, "client")
        assert agent.client is not None


# Made with Bob
