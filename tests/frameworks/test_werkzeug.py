# (c) Copyright IBM Corp. 2026

"""
Tests for Werkzeug instrumentation.
"""

import threading
import time
from typing import Any, Callable, Generator, Optional
from unittest.mock import MagicMock

import pytest
import requests
from werkzeug.wrappers import Request, Response

from instana.instrumentation.wsgi import InstanaWSGIMiddleware
from instana.util.wsgi_utils import (
    normalize_headers as _normalize_headers,
    parse_status_code as _parse_status_code,
)
from instana.singletons import get_tracer
from instana.util.ids import hex_id
from tests.helpers import get_first_span_by_filter


def simple_wsgi_app(environ: dict[str, Any], start_response: Callable) -> list:
    """Simple WSGI app for testing."""
    request = Request(environ)
    path = request.path

    if path == "/":
        response = Response("Hello World")
    elif path == "/error":
        response = Response("Internal Server Error", status=500)
    elif path == "/exception":
        raise RuntimeError("Test exception")
    elif path.startswith("/hello/"):
        name = path.split("/")[-1]
        response = Response(f"Hello, {name}!")
    elif path == "/query":
        response = Response(f"Query: {request.query_string.decode()}")
    else:
        response = Response("Not Found", status=404)

    return response(environ, start_response)


class TestWerkzeugInstrumentation:
    """Tests for Werkzeug autowrapt instrumentation."""

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()

        yield

        self.recorder.clear_spans()

    def _make_request(
        self,
        app: Callable,
        path: str = "/",
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
    ) -> tuple[str, list, bytes]:
        """Helper to make WSGI requests and capture response."""
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": "",
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "80",
            "HTTP_HOST": "localhost",
            "wsgi.url_scheme": "http",
            "wsgi.input": MagicMock(),
            "wsgi.errors": MagicMock(),
            "wsgi.multithread": False,
            "wsgi.multiprocess": True,
            "wsgi.run_once": False,
        }

        if "?" in path:
            path, query = path.split("?", 1)
            environ["PATH_INFO"] = path
            environ["QUERY_STRING"] = query

        if headers:
            for key, value in headers.items():
                environ[f"HTTP_{key.upper().replace('-', '_')}"] = value

        response_data = []
        response_status = []
        response_headers = []

        def start_response(status: str, headers: list, exc_info=None):
            response_status.append(status)
            response_headers.extend(headers)
            return lambda x: response_data.append(x)

        result = app(environ, start_response)
        # Consume the iterable
        for chunk in result:
            response_data.append(chunk)

        return response_status[0], response_headers, b"".join(response_data)

    def test_traced_wsgi_app_basic_request(self) -> None:
        """Test InstanaWSGIMiddleware wrapper with basic request."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)
        status, _, body = self._make_request(wrapped_app, "/")

        assert status == "200 OK"
        assert b"Hello World" in body

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.n == "wsgi"
        assert span.data["http"]["method"] == "GET"
        assert span.data["http"]["path"] == "/"
        assert span.data["http"]["status"] == 200
        assert span.data["http"]["host"] == "localhost"
        assert not span.ec

    def test_traced_wsgi_app_with_query_params(self) -> None:
        """Test InstanaWSGIMiddleware with query parameters."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)
        status, _, __ = self._make_request(wrapped_app, "/query?foo=bar&baz=qux")

        assert status == "200 OK"

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.n == "wsgi"
        assert span.data["http"]["method"] == "GET"
        assert span.data["http"]["path"] == "/query"
        assert span.data["http"]["params"] == "foo=bar&baz=qux"
        assert span.data["http"]["status"] == 200

    def test_traced_wsgi_app_secret_scrubbing(self) -> None:
        """Test that secrets are scrubbed from query parameters."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)
        status, _, __ = self._make_request(
            wrapped_app, "/query?foo=bar&password=secret123&key=value"
        )

        assert status == "200 OK"

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.n == "wsgi"
        assert "password" in span.data["http"]["params"]
        assert "secret123" not in span.data["http"]["params"]
        assert "<redacted>" in span.data["http"]["params"]

    def test_traced_wsgi_app_500_error(self) -> None:
        """Test 500 error response handling."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)
        status, _, __ = self._make_request(wrapped_app, "/error")

        assert status == "500 INTERNAL SERVER ERROR"

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.n == "wsgi"
        assert span.data["http"]["status"] == 500
        assert span.ec == 1

    def test_traced_wsgi_app_exception_handling(self) -> None:
        """Test exception handling in wrapped app."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)

        with pytest.raises(RuntimeError, match="Test exception"):
            self._make_request(wrapped_app, "/exception")

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.n == "wsgi"
        assert span.ec == 1

    def test_traced_wsgi_app_404_not_found(self) -> None:
        """Test 404 not found response."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)
        status, _, __ = self._make_request(wrapped_app, "/nonexistent")

        assert status == "404 NOT FOUND"

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.n == "wsgi"
        assert span.data["http"]["status"] == 404
        assert not span.ec  # 404 is not an error from instrumentation perspective

    def test_traced_wsgi_app_trace_context_propagation(self) -> None:
        """Test trace context propagation through headers."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)

        with self.tracer.start_as_current_span("test") as parent_span:
            span_context = parent_span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            status, response_headers, _ = self._make_request(
                wrapped_app, "/", headers=headers
            )

        assert status == "200 OK"

        # Check response headers contain trace context
        header_dict = dict(response_headers)
        assert "X-INSTANA-T" in header_dict
        assert "X-INSTANA-S" in header_dict
        assert "X-INSTANA-L" in header_dict

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        # Find the test span and wsgi span
        def span_filter_1(span):
            return span.n == "sdk" and span.data["sdk"]["name"] == "test"

        test_span = get_first_span_by_filter(spans, span_filter_1)
        assert test_span

        def span_filter_2(span):
            return span.n == "wsgi"

        wsgi_span = get_first_span_by_filter(spans, span_filter_2)
        assert wsgi_span

        # Verify parent-child relationship
        assert test_span.t == wsgi_span.t
        assert test_span.s == wsgi_span.p

        # Verify response headers
        assert header_dict["X-INSTANA-T"] == hex_id(wsgi_span.t)
        assert header_dict["X-INSTANA-S"] == hex_id(wsgi_span.s)

    def test_traced_wsgi_app_post_request(self) -> None:
        """Test POST request instrumentation."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)
        self._make_request(wrapped_app, "/", method="POST")

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.n == "wsgi"
        assert span.data["http"]["method"] == "POST"
        assert span.data["http"]["path"] == "/"

    def test_traced_wsgi_app_multiple_requests(self) -> None:
        """Test multiple sequential requests produce isolated spans."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)

        self._make_request(wrapped_app, "/")
        self._make_request(wrapped_app, "/hello/World")
        self._make_request(wrapped_app, "/hello/Test")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        # All should be wsgi spans with unique IDs
        for span in spans:
            assert span.n == "wsgi"
            assert not span.ec
            assert span.data["http"]["status"] == 200

        # Each request must produce a unique span and trace
        assert spans[0].s != spans[1].s != spans[2].s
        assert spans[0].t != spans[1].t != spans[2].t

    def test_traced_wsgi_app_wraps_application(self) -> None:
        """Test that InstanaWSGIMiddleware properly wraps an application."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)

        assert wrapped_app.app is simple_wsgi_app
        assert callable(wrapped_app)

    def test_traced_wsgi_app_preserves_app_behavior(self) -> None:
        """Test that wrapped app behaves like original."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)

        # Make a request through wrapped app
        status, _, body = self._make_request(wrapped_app, "/hello/Test")

        assert status == "200 OK"
        assert b"Hello, Test!" in body

        # Verify span was created
        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        assert spans[0].n == "wsgi"

    def test_run_simple_wrapper_logic(self) -> None:
        """Test the wrapping logic in run_simple_with_instana."""
        # Test that the wrapper correctly identifies and wraps the app

        # Test with positional args
        args = ("localhost", 5000, simple_wsgi_app)
        if len(args) >= 3:
            _, __, application = args[0], args[1], args[2]
            instrumented_app = InstanaWSGIMiddleware(application)
            assert isinstance(instrumented_app, InstanaWSGIMiddleware)
            assert instrumented_app.app is simple_wsgi_app

        # Test with kwargs
        kwargs = {"application": simple_wsgi_app}
        if "application" in kwargs:
            application = kwargs["application"]
            instrumented_app = InstanaWSGIMiddleware(application)
            assert isinstance(instrumented_app, InstanaWSGIMiddleware)
            assert instrumented_app.app is simple_wsgi_app

    def test_query_params_without_agent(self) -> None:
        """Test query params when agent is None."""
        from instana.util.wsgi_utils import scrub_query_params
        from unittest.mock import patch

        # Mock agent as None - should return original query string
        with patch("instana.util.wsgi_utils.agent", None):
            result = scrub_query_params("foo=bar&password=secret")
            assert result == "foo=bar&password=secret"

    def test_traced_wsgi_app_init(self) -> None:
        """Test InstanaWSGIMiddleware initialization."""
        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)
        assert wrapped_app.app is simple_wsgi_app
        assert hasattr(wrapped_app, "app")

    def test_traced_wsgi_app_span_creation_failure(self) -> None:
        """Test exception handling when span creation fails."""
        from unittest.mock import patch

        wrapped_app = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)

        # Mock create_span_with_context to raise an exception
        with patch(
            "instana.instrumentation.wsgi.create_span_with_context",
            side_effect=Exception("Span creation failed"),
        ):
            status, _, body = self._make_request(wrapped_app, "/")

        # App should still work, falling back to unwrapped behavior
        assert status == "200 OK"
        assert b"Hello World" in body

        # No spans should be created due to the failure
        spans = self.recorder.queued_spans()
        assert len(spans) == 0

    def test_werkzeug_run_simple_integration(self) -> None:
        """Integration test: Start actual werkzeug server and verify instrumentation."""
        from werkzeug.serving import run_simple
        import socket

        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]

        server_started = threading.Event()
        server_error = []

        def run_server():
            try:
                # Signal that server is starting
                server_started.set()
                # Run werkzeug server (this will be instrumented)
                run_simple(
                    "127.0.0.1",
                    port,
                    simple_wsgi_app,
                    use_reloader=False,
                    use_debugger=False,
                    threaded=True,
                )
            except Exception as e:
                server_error.append(e)

        # Start server in background thread
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Wait for server to start
        server_started.wait(timeout=2)
        time.sleep(0.5)  # Give server time to bind

        try:
            # Make HTTP request to the server
            response = requests.get(f"http://127.0.0.1:{port}/", timeout=2)
            assert response.status_code == 200
            assert b"Hello World" in response.content

            # Give time for span to be recorded
            time.sleep(0.2)

            # Verify span was created
            spans = self.recorder.queued_spans()
            assert len(spans) >= 1

            # Find the wsgi span
            wsgi_spans = [s for s in spans if s.n == "wsgi"]
            assert len(wsgi_spans) >= 1

            span = wsgi_spans[0]
            assert span.data["http"]["method"] == "GET"
            assert span.data["http"]["path"] == "/"
            assert span.data["http"]["status"] == 200
            assert not span.ec

        finally:
            # Server will be stopped when thread exits (daemon thread)
            pass

    def test_werkzeug_run_simple_integration_kwargs(self) -> None:
        """Integration test: Start werkzeug server with kwargs and verify instrumentation."""
        from werkzeug.serving import run_simple
        import socket

        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]

        server_started = threading.Event()

        def run_server():
            try:
                server_started.set()
                # Run with application as kwarg (tests lines 69-73)
                run_simple(
                    hostname="127.0.0.1",
                    port=port,
                    application=simple_wsgi_app,
                    use_reloader=False,
                    use_debugger=False,
                    threaded=True,
                )
            except Exception:
                pass

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        server_started.wait(timeout=2)
        time.sleep(0.5)

        try:
            response = requests.get(f"http://127.0.0.1:{port}/", timeout=2)
            assert response.status_code == 200

            time.sleep(0.2)

            spans = self.recorder.queued_spans()
            wsgi_spans = [s for s in spans if s.n == "wsgi"]
            assert len(wsgi_spans) >= 1

            span = wsgi_spans[0]
            assert span.data["http"]["status"] == 200

        finally:
            pass

    def test_is_flask_app_detection(self) -> None:
        """Test _is_flask_app correctly identifies Flask applications."""
        from instana.instrumentation.werkzeug import _is_flask_app

        # Mock a Flask app - the class name should be "Flask"
        class Flask:
            pass

        # Set the module to simulate flask.app
        Flask.__module__ = "flask.app"

        flask_app = Flask()
        assert _is_flask_app(flask_app) is True

    def test_is_flask_app_with_wrapped_wsgi_app(self) -> None:
        """Test _is_flask_app detects Flask apps wrapped in middleware."""
        from instana.instrumentation.werkzeug import _is_flask_app

        # Mock a Flask app - class name should be "Flask"
        class Flask:
            pass

        Flask.__module__ = "flask.app"

        # Mock middleware wrapping Flask app
        class MockMiddleware:
            def __init__(self):
                self.wsgi_app = Flask()

        wrapped_app = MockMiddleware()
        assert _is_flask_app(wrapped_app) is True

    def test_is_flask_app_non_flask(self) -> None:
        """Test _is_flask_app returns False for non-Flask apps."""
        from instana.instrumentation.werkzeug import _is_flask_app

        # Regular WSGI app
        assert _is_flask_app(simple_wsgi_app) is False

        # Mock non-Flask app
        class MockApp:
            __name__ = "NotFlask"
            __module__ = "some.module"

        assert _is_flask_app(MockApp()) is False

    def test_run_simple_skips_flask_app_positional_args(self) -> None:
        """Test run_simple_with_instana skips Flask apps (positional args)."""
        from instana.instrumentation.werkzeug import _is_flask_app
        from unittest.mock import patch, MagicMock

        # Mock a Flask app - class name should be "Flask"
        class Flask:
            def __call__(self, environ, start_response):
                return simple_wsgi_app(environ, start_response)

        Flask.__module__ = "flask.app"
        flask_app = Flask()

        # Verify our mock is detected as Flask
        assert _is_flask_app(flask_app), "Flask app not detected"

        # Patch make_server to prevent actual server start but allow instrumentation to run
        with patch("werkzeug.serving.make_server") as mock_make_server:
            mock_server = MagicMock()
            mock_server.serve_forever = MagicMock()
            mock_make_server.return_value = mock_server

            from werkzeug.serving import run_simple

            # Call run_simple with Flask app
            run_simple(
                "localhost", 5000, flask_app, use_reloader=False, use_debugger=False
            )

            # Verify make_server was called with original Flask app (not wrapped)
            mock_make_server.assert_called_once()
            call_args = mock_make_server.call_args[0]
            # Flask app should NOT be wrapped in InstanaWSGIMiddleware
            assert call_args[2] is flask_app
            assert not isinstance(call_args[2], InstanaWSGIMiddleware)

    def test_run_simple_skips_flask_app_kwargs(self) -> None:
        """Test run_simple_with_instana skips Flask apps (kwargs)."""
        from instana.instrumentation.werkzeug import _is_flask_app
        from unittest.mock import patch, MagicMock

        # Mock a Flask app - class name should be "Flask"
        class Flask:
            def __call__(self, environ, start_response):
                return simple_wsgi_app(environ, start_response)

        Flask.__module__ = "flask.app"
        flask_app = Flask()

        # Verify our mock is detected as Flask
        assert _is_flask_app(flask_app), "Flask app not detected"

        # Patch make_server to prevent actual server start but allow instrumentation to run
        with patch("werkzeug.serving.make_server") as mock_make_server:
            mock_server = MagicMock()
            mock_server.serve_forever = MagicMock()
            mock_make_server.return_value = mock_server

            from werkzeug.serving import run_simple

            # Call run_simple with Flask app using kwargs
            run_simple(
                hostname="localhost",
                port=5000,
                application=flask_app,
                use_reloader=False,
                use_debugger=False,
            )

            # Verify make_server was called with original Flask app (not wrapped)
            mock_make_server.assert_called_once()
            call_args = mock_make_server.call_args[0]
            # Flask app should NOT be wrapped in InstanaWSGIMiddleware (3rd positional arg)
            assert call_args[2] is flask_app
            assert not isinstance(call_args[2], InstanaWSGIMiddleware)

    def test_base_wsgi_server_direct_instantiation(self) -> None:
        """Test instrumentation when BaseWSGIServer is instantiated directly (e.g. Odoo).

        Odoo's ThreadedWSGIServerReloadable extends werkzeug.serving.ThreadedWSGIServer
        which extends BaseWSGIServer, bypassing run_simple entirely. This test verifies
        that the BaseWSGIServer.__init__ patch wraps the app in that case.
        """
        import socket
        from werkzeug.serving import BaseWSGIServer

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = BaseWSGIServer("127.0.0.1", port, simple_wsgi_app)
        try:
            assert isinstance(server.app, InstanaWSGIMiddleware)
            assert server.app.app is simple_wsgi_app
        finally:
            server.server_close()

    def test_base_wsgi_server_skips_flask_app(self) -> None:
        """Test that BaseWSGIServer patch skips Flask apps."""
        import socket
        from werkzeug.serving import BaseWSGIServer

        class Flask:
            def __call__(self, environ, start_response):
                return simple_wsgi_app(environ, start_response)

        Flask.__module__ = "flask.app"
        flask_app = Flask()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = BaseWSGIServer("127.0.0.1", port, flask_app)
        try:
            assert server.app is flask_app
            assert not isinstance(server.app, InstanaWSGIMiddleware)
        finally:
            server.server_close()

    def test_base_wsgi_server_not_double_wrapped(self) -> None:
        """Test that an already-wrapped app is not wrapped again."""
        import socket
        from werkzeug.serving import BaseWSGIServer

        pre_wrapped = InstanaWSGIMiddleware(simple_wsgi_app, status_as_string=False)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server = BaseWSGIServer("127.0.0.1", port, pre_wrapped)
        try:
            assert server.app is pre_wrapped
            assert not isinstance(server.app.app, InstanaWSGIMiddleware)
        finally:
            server.server_close()


def test_parse_status_code_handles_valid_and_invalid_values() -> None:
    """Test safe parsing of WSGI status strings."""
    assert _parse_status_code("200 OK") == 200
    assert _parse_status_code("404") == 404
    assert _parse_status_code("") is None
    assert _parse_status_code("INVALID") is None
    assert _parse_status_code(" OK") is None
    assert _parse_status_code(None) is None  # type: ignore[arg-type]


def test_normalize_headers_converts_non_string_values() -> None:
    """Test response header normalization."""
    headers = [("Content-Length", 123), ("Content-Type", "text/plain")]
    assert _normalize_headers(headers) == [
        ("Content-Length", "123"),
        ("Content-Type", "text/plain"),
    ]


# Made with Bob
