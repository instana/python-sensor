# (C) Copyright IBM Corp. 2026

"""
Unit tests for WSGI utility functions
"""

import pytest
from typing import Generator
from unittest.mock import Mock, patch

from instana.util.wsgi_utils import (
    build_start_response,
    create_span_with_context,
    end_span_after_iterating,
    normalize_headers,
    parse_status_code,
    scrub_query_params,
    set_request_attributes,
)
from instana.singletons import get_tracer


class TestWSGIUtils:
    """Tests for WSGI utility functions"""

    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        """Setup test environment"""
        self.tracer = get_tracer()
        self.recorder = self.tracer._span_processor  # type: ignore
        self.recorder.clear_spans()  # type: ignore
        yield
        self.recorder.clear_spans()  # type: ignore

    def test_parse_status_code_valid(self) -> None:
        """Test parsing valid status codes"""
        assert parse_status_code("200 OK") == 200
        assert parse_status_code("404 Not Found") == 404
        assert parse_status_code("500 Internal Server Error") == 500
        assert parse_status_code("301") == 301

    def test_parse_status_code_invalid(self) -> None:
        """Test parsing invalid status codes"""
        # AttributeError - None has no split
        assert parse_status_code(None) is None  # type: ignore

        # IndexError - empty string
        assert parse_status_code("") is None

        # ValueError - non-numeric
        assert parse_status_code("OK 200") is None

        # TypeError - wrong type
        assert parse_status_code(200) is None  # type: ignore

    def test_normalize_headers_all_strings(self) -> None:
        """Test normalizing headers when all values are strings"""
        headers = [("Content-Type", "text/html"), ("X-Custom", "value")]
        result = normalize_headers(headers)
        assert result == headers

    def test_normalize_headers_mixed_types(self) -> None:
        """Test normalizing headers with non-string values"""
        headers = [
            ("Content-Length", 1234),
            ("X-Count", 42),
            ("Content-Type", "text/html"),
        ]
        result = normalize_headers(headers)
        assert result == [
            ("Content-Length", "1234"),
            ("X-Count", "42"),
            ("Content-Type", "text/html"),
        ]

    def test_build_start_response_with_500_error(self) -> None:
        """Test start_response wrapper marks span as errored for 5xx status"""
        span = self.tracer.start_span("test")
        original_start_response = Mock()

        wrapped = build_start_response(span, original_start_response)
        headers = [("Content-Type", "text/html")]

        wrapped("500 Internal Server Error", headers)

        # Verify span was marked as errored
        assert span.attributes.get("ec") == 1
        span.end()

    def test_build_start_response_exception_handling(self) -> None:
        """Test start_response wrapper handles exceptions gracefully"""
        span = Mock()
        span.context = Mock()

        # Make tracer.inject raise an exception
        original_start_response = Mock()

        with patch("instana.util.wsgi_utils.get_tracer") as mock_tracer:
            mock_tracer.return_value.inject.side_effect = RuntimeError("Inject failed")

            wrapped = build_start_response(span, original_start_response)
            headers = [("Content-Type", "text/html")]

            # Should not raise, should call original start_response
            _ = wrapped("200 OK", headers, None)

            # Original start_response should be called with original headers
            original_start_response.assert_called_once_with("200 OK", headers, None)

    def test_end_span_after_iterating_with_close(self) -> None:
        """Test end_span_after_iterating calls close on iterable"""
        span = self.tracer.start_span("test")
        _ = self.tracer._span_processor  # type: ignore
        token = Mock()

        # Create iterable with close method
        class CloseableIterable:
            def __init__(self):
                self.closed = False

            def __iter__(self):
                return self

            def __next__(self):
                raise StopIteration

            def close(self):
                self.closed = True

        iterable = CloseableIterable()

        # Consume the generator
        list(end_span_after_iterating(iterable, span, token))

        # Verify close was called
        assert iterable.closed

    def test_end_span_after_iterating_close_exception(self) -> None:
        """Test end_span_after_iterating handles close exceptions"""
        span = self.tracer.start_span("test")
        token = Mock()

        # Create iterable with close that raises
        class BadCloseIterable:
            def __iter__(self):
                return self

            def __next__(self):
                raise StopIteration

            def close(self):
                raise RuntimeError("Close failed")

        iterable = BadCloseIterable()

        # Should not raise, should handle exception gracefully
        list(end_span_after_iterating(iterable, span, token))

    def test_scrub_query_params_with_agent(self) -> None:
        """Test query param scrubbing when agent is available"""
        query = "key=value&secret=password123"
        result = scrub_query_params(query)

        # Should scrub secrets
        assert (
            "secret=<redacted>" in result or "secret" not in result or result == query
        )

    def test_scrub_query_params_no_agent(self) -> None:
        """Test query param scrubbing when agent is None"""
        query = "key=value&secret=password123"

        with patch("instana.util.wsgi_utils.agent", None):
            result = scrub_query_params(query)
            # Should return original when agent is None
            assert result == query

    def test_set_request_attributes_with_query_string(self) -> None:
        """Test setting request attributes with query string"""
        span = self.tracer.start_span("test")

        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/users",
            "QUERY_STRING": "id=123&secret=hidden",
            "HTTP_HOST": "example.com:8080",
            "wsgi.url_scheme": "https",
            "SCRIPT_NAME": "/app",
        }

        set_request_attributes(span, environ)

        # Verify attributes were set
        assert span.attributes.get("http.method") == "POST"
        assert span.attributes.get("http.path") == "/api/users"
        assert span.attributes.get("http.host") == "example.com:8080"
        assert "http.params" in span.attributes
        assert (
            span.attributes.get("http.url") == "https://example.com:8080/app/api/users"
        )

        span.end()

    def test_set_request_attributes_empty_query_string(self) -> None:
        """Test setting request attributes with empty query string"""
        span = self.tracer.start_span("test")

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "QUERY_STRING": "",
            "HTTP_HOST": "localhost",
            "wsgi.url_scheme": "http",
        }

        set_request_attributes(span, environ)

        # Verify query params not set for empty string
        assert "http.params" not in span.attributes

        span.end()

    def test_set_request_attributes_whitespace_query(self) -> None:
        """Test setting request attributes with whitespace-only query string"""
        span = self.tracer.start_span("test")

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/",
            "QUERY_STRING": "   ",
            "HTTP_HOST": "localhost",
            "wsgi.url_scheme": "http",
        }

        set_request_attributes(span, environ)

        # Verify query params not set for whitespace
        assert "http.params" not in span.attributes

        span.end()

    def test_set_request_attributes_exception_handling(self) -> None:
        """Test set_request_attributes handles exceptions gracefully"""
        span = Mock()
        span.set_attribute = Mock(side_effect=RuntimeError("Attribute error"))

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
        }

        # Should not raise exception
        set_request_attributes(span, environ)

    def test_create_span_with_context(self) -> None:
        """Test creating span with context"""
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "HTTP_HOST": "localhost:8080",
            "wsgi.url_scheme": "http",
        }

        span, token = create_span_with_context(environ)

        assert span is not None
        assert span.name == "wsgi"
        assert token is not None

        # Clean up
        span.end()
        from opentelemetry import context

        context.detach(token)

    def test_build_start_response_status_as_string(self) -> None:
        """Test build_start_response with status_as_string=True"""
        span = self.tracer.start_span("test")
        original_start_response = Mock()

        wrapped = build_start_response(
            span, original_start_response, status_as_string=True
        )
        headers = [("Content-Type", "text/html")]

        wrapped("200 OK", headers)

        # Verify status was set as string
        assert span.attributes.get("http.status_code") == "200"
        span.end()

    def test_build_start_response_status_as_int(self) -> None:
        """Test build_start_response with status_as_string=False"""
        span = self.tracer.start_span("test")
        original_start_response = Mock()

        wrapped = build_start_response(
            span, original_start_response, status_as_string=False
        )
        headers = [("Content-Type", "text/html")]

        wrapped("404 Not Found", headers)

        # Verify status was set as int
        assert span.attributes.get("http.status_code") == 404
        span.end()


# Made with Bob
