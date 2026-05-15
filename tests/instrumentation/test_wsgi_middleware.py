# (C) Copyright IBM Corp. 2026

"""
Unit tests for InstanaWSGIMiddleware class
"""

import pytest
from typing import Any, Callable, Generator
from unittest.mock import Mock, patch

from instana.instrumentation.wsgi import InstanaWSGIMiddleware
from instana.singletons import get_tracer


class TestInstanaWSGIMiddleware:
    """Direct unit tests for InstanaWSGIMiddleware"""

    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        """Setup test environment"""
        self.tracer = get_tracer()
        self.recorder = self.tracer._span_processor  # type: ignore
        self.recorder.clear_spans()  # type: ignore
        yield
        self.recorder.clear_spans()  # type: ignore

    def test_middleware_init(self) -> None:
        """Test middleware initialization"""
        app = Mock()
        middleware = InstanaWSGIMiddleware(app)
        assert middleware.app is app

    def test_middleware_call_success(self) -> None:
        """Test successful middleware call"""
        # Create mock app
        app = Mock()
        app.return_value = [b"response"]

        # Create middleware
        middleware = InstanaWSGIMiddleware(app)

        # Create environ
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "HTTP_HOST": "localhost:8080",
            "wsgi.url_scheme": "http",
        }

        # Create start_response
        start_response = Mock()

        # Call middleware
        result = middleware(environ, start_response)

        # Consume the generator
        _ = list(result)  # type: ignore

        # Verify app was called
        assert app.called
        spans = self.recorder.queued_spans()  # type: ignore
        assert len(spans) == 1
        assert spans[0].n == "wsgi"

    def test_middleware_call_with_exception_in_span_creation(self) -> None:
        """Test middleware when span creation fails"""
        app = Mock()
        app.return_value = [b"response"]

        middleware = InstanaWSGIMiddleware(app)

        environ = {"REQUEST_METHOD": "GET"}
        start_response = Mock()

        # Mock create_span_with_context to raise exception
        with patch(
            "instana.instrumentation.wsgi.create_span_with_context",
            side_effect=Exception("Span creation failed"),
        ):
            result = middleware(environ, start_response)

            # Should return app result directly
            assert result == app.return_value
            # App should be called with original start_response
            app.assert_called_once_with(environ, start_response)

    def test_middleware_call_with_exception_in_app(self) -> None:
        """Test middleware when app raises exception"""
        app = Mock()
        app.side_effect = ValueError("App error")

        middleware = InstanaWSGIMiddleware(app)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "HTTP_HOST": "localhost:8080",
            "wsgi.url_scheme": "http",
        }
        start_response = Mock()

        # Call middleware and expect exception
        with pytest.raises(ValueError, match="App error"):
            middleware(environ, start_response)

        # Verify span was recorded with exception
        spans = self.recorder.queued_spans()  # type: ignore
        assert len(spans) == 1
        span = spans[0]
        assert span.n == "wsgi"
        # Exception should be recorded (ec is error count)
        assert span.ec == 1

    def test_middleware_call_with_exception_in_app_no_span(self) -> None:
        """Test middleware when app raises exception and span is None"""
        app = Mock()
        app.side_effect = RuntimeError("App runtime error")

        middleware = InstanaWSGIMiddleware(app)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "HTTP_HOST": "localhost:8080",
            "wsgi.url_scheme": "http",
        }
        start_response = Mock()

        # Mock create_span_with_context to return None span
        with (
            patch(
                "instana.instrumentation.wsgi.create_span_with_context",
                return_value=(None, None),
            ),
            pytest.raises(RuntimeError, match="App runtime error"),
        ):
            middleware(environ, start_response)

    def test_middleware_call_with_exception_span_not_recording(self) -> None:
        """Test middleware when app raises exception and span is not recording"""
        app = Mock()
        app.side_effect = KeyError("Key not found")

        middleware = InstanaWSGIMiddleware(app)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "HTTP_HOST": "localhost:8080",
            "wsgi.url_scheme": "http",
        }
        start_response = Mock()

        # Mock span that is not recording
        mock_span = Mock()
        mock_span.is_recording.return_value = False
        mock_token = Mock()

        with patch(
            "instana.instrumentation.wsgi.create_span_with_context",
            return_value=(mock_span, mock_token),
        ):
            with pytest.raises(KeyError, match="Key not found"):
                middleware(environ, start_response)

            # Verify span.end() was not called since not recording
            mock_span.end.assert_not_called()

    def test_middleware_call_with_token_detach(self) -> None:
        """Test middleware properly detaches context token on exception"""
        app = Mock()
        app.side_effect = TypeError("Type error")

        middleware = InstanaWSGIMiddleware(app)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "HTTP_HOST": "localhost:8080",
            "wsgi.url_scheme": "http",
        }
        start_response = Mock()

        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_token = Mock()

        with (
            patch(
                "instana.instrumentation.wsgi.create_span_with_context",
                return_value=(mock_span, mock_token),
            ),
            patch("instana.instrumentation.wsgi.context") as mock_context,
            pytest.raises(TypeError, match="Type error"),
        ):
            middleware(environ, start_response)

            # Verify context.detach was called
            mock_context.detach.assert_called_once_with(mock_token)

    def test_middleware_call_with_no_token(self) -> None:
        """Test middleware when token is None"""
        app = Mock()
        app.side_effect = AttributeError("Attribute error")

        middleware = InstanaWSGIMiddleware(app)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "HTTP_HOST": "localhost:8080",
            "wsgi.url_scheme": "http",
        }
        start_response = Mock()

        mock_span = Mock()
        mock_span.is_recording.return_value = True

        with (
            patch(
                "instana.instrumentation.wsgi.create_span_with_context",
                return_value=(mock_span, None),
            ),
            patch("instana.instrumentation.wsgi.context") as mock_context,
            pytest.raises(AttributeError, match="Attribute error"),
        ):
            middleware(environ, start_response)

            # Verify context.detach was not called since token is None
            mock_context.detach.assert_not_called()

    def test_middleware_integration_with_iterable(self) -> None:
        """Test middleware with iterable response"""

        def app(environ: dict[str, Any], start_response: Callable) -> list[bytes]:
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"Hello", b" ", b"World"]

        middleware = InstanaWSGIMiddleware(app)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "HTTP_HOST": "localhost:8080",
            "wsgi.url_scheme": "http",
        }

        start_response_called = []

        def start_response(
            status: str, headers: list[tuple[str, str]], exc_info: Any = None
        ) -> None:
            start_response_called.append((status, headers))

        result = middleware(environ, start_response)

        # Consume the generator
        response_data = b"".join(result)  # type: ignore

        assert response_data == b"Hello World"
        assert len(start_response_called) == 1
        assert start_response_called[0][0] == "200 OK"

        # Verify span was created
        spans = self.recorder.queued_spans()  # type: ignore
        assert len(spans) == 1
        assert spans[0].n == "wsgi"


# Made with Bob
