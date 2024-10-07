# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import pytest
from typing import Generator
from sanic_testing.testing import SanicTestClient

from instana.singletons import tracer, agent
from instana.util.ids import hex_id
from tests.helpers import get_first_span_by_filter
from tests.test_utils import _TraceContextMixin
from tests.apps.sanic_app.server import app


class TestSanic(_TraceContextMixin):
    @classmethod
    def setup_class(cls) -> None:
        cls.client = SanicTestClient(app, port=1337, host="127.0.0.1")

        # Hack together a manual custom headers list; We'll use this in tests
        agent.options.extra_http_headers = [
            "X-Capture-This",
            "X-Capture-That",
            "X-Capture-This-Too",
            "X-Capture-That-Too",
        ]

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup and Teardown"""
        # setup
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

    def test_vanilla_get(self) -> None:
        request, response = self.client.get("/")

        assert response.status_code == 200
        assert "X-INSTANA-T" in response.headers
        assert "X-INSTANA-S" in response.headers
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        assert spans[0].n == "asgi"

    def test_basic_get(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            request, response = self.client.get("/", headers=headers)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_404(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            request, response = self.client.get("/foo/not_an_int", headers=headers)

        assert response.status_code == 404

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/foo/not_an_int"
        assert not asgi_span.data["http"]["path_tpl"]
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 404
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_sanic_exception(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            request, response = self.client.get("/wrong", headers=headers)

        assert response.status_code == 400

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/wrong"
        assert asgi_span.data["http"]["path_tpl"] == "/wrong"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 400
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_500_instana_exception(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            request, response = self.client.get("/instana_exception", headers=headers)

        assert response.status_code == 500

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert asgi_span.ec == 1
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/instana_exception"
        assert asgi_span.data["http"]["path_tpl"] == "/instana_exception"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 500
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_500(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            request, response = self.client.get("/test_request_args", headers=headers)

        assert response.status_code == 500

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert asgi_span.ec == 1
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/test_request_args"
        assert asgi_span.data["http"]["path_tpl"] == "/test_request_args"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 500
        assert asgi_span.data["http"]["error"] == "Something went wrong."
        assert not asgi_span.data["http"]["params"]

    def test_path_templates(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            request, response = self.client.get("/foo/1", headers=headers)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/foo/1"
        assert asgi_span.data["http"]["path_tpl"] == "/foo/<foo_id:int>"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_secret_scrubbing(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            request, response = self.client.get("/?secret=shhh", headers=headers)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert asgi_span.data["http"]["params"] == "secret=<redacted>"

    def test_synthetic_request(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
                "X-INSTANA-SYNTHETIC": "1",
            }
            request, response = self.client.get("/", headers=headers)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert asgi_span.sy
        assert not test_span.sy

    def test_request_header_capture(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
                "X-Capture-This": "this",
                "X-Capture-That": "that",
            }
            request, response = self.client.get("/", headers=headers)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert "X-Capture-This" in asgi_span.data["http"]["header"]
        assert "this" == asgi_span.data["http"]["header"]["X-Capture-This"]
        assert "X-Capture-That" in asgi_span.data["http"]["header"]
        assert "that" == asgi_span.data["http"]["header"]["X-Capture-That"]

    def test_response_header_capture(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As SanicTestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the sanic server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            request, response = self.client.get("/response_headers", headers=headers)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/response_headers"
        assert asgi_span.data["http"]["path_tpl"] == "/response_headers"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200

        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert "X-Capture-This-Too" in asgi_span.data["http"]["header"]
        assert "this too" == asgi_span.data["http"]["header"]["X-Capture-This-Too"]
        assert "X-Capture-That-Too" in asgi_span.data["http"]["header"]
        assert "that too" == asgi_span.data["http"]["header"]["X-Capture-That-Too"]
