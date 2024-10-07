# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from typing import Generator

from fastapi.testclient import TestClient
import pytest
from instana.singletons import tracer, agent

from instana.util.ids import hex_id
from tests.apps.fastapi_app.app import fastapi_server
from tests.helpers import get_first_span_by_filter


class TestFastAPI:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # We are using the TestClient from Starlette/FastAPI to make it easier.
        self.client = TestClient(fastapi_server)

        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # Hack together a manual custom headers list; We'll use this in tests
        agent.options.extra_http_headers = [
            "X-Capture-This",
            "X-Capture-That",
            "X-Capture-This-Too",
            "X-Capture-That-Too",
        ]

    def test_vanilla_get(self) -> None:
        result = self.client.get("/")

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        # FastAPI instrumentation (like all instrumentation) _always_ traces
        # unless told otherwise
        spans = self.recorder.queued_spans()

        assert len(spans) == 1
        assert spans[0].n == "asgi"

    def test_basic_get(self) -> None:
        result = None
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/", headers=headers)

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "testserver"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200

        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_400(self) -> None:
        result = None
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/400", headers=headers)

        assert result
        assert result.status_code == 400
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "testserver"
        assert asgi_span.data["http"]["path"] == "/400"
        assert asgi_span.data["http"]["path_tpl"] == "/400"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 400

        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_500(self) -> None:
        result = None
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/500", headers=headers)

        assert result
        assert result.status_code == 500
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert asgi_span.ec == 1
        assert asgi_span.data["http"]["host"] == "testserver"
        assert asgi_span.data["http"]["path"] == "/500"
        assert asgi_span.data["http"]["path_tpl"] == "/500"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 500
        assert asgi_span.data["http"]["error"] == "500 response"
        assert not asgi_span.data["http"]["params"]

    def test_path_templates(self) -> None:
        result = None
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/users/1", headers=headers)

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "testserver"
        assert asgi_span.data["http"]["path"] == "/users/1"
        assert asgi_span.data["http"]["path_tpl"] == "/users/{user_id}"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_secret_scrubbing(self) -> None:
        result = None
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/?secret=shhh", headers=headers)

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "testserver"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200

        assert not asgi_span.data["http"]["error"]
        assert asgi_span.data["http"]["params"] == "secret=<redacted>"

    def test_synthetic_request(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
                "X-INSTANA-SYNTHETIC": "1",
            }
            result = self.client.get("/", headers=headers)

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "testserver"
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
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
                "X-Capture-This": "this", 
                "X-Capture-That": "that",
            }
            result = self.client.get("/", headers=headers)

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)        
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "testserver"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200

        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert "X-Capture-This" in asgi_span.data["http"]["header"]
        assert asgi_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert "X-Capture-That" in asgi_span.data["http"]["header"]
        assert asgi_span.data["http"]["header"]["X-Capture-That"] == "that"

    def test_response_header_capture(self) -> None:
        # The background FastAPI server is pre-configured with custom headers 
        # to capture.

        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/response_headers", headers=headers)

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "testserver"
        assert asgi_span.data["http"]["path"] == "/response_headers"
        assert asgi_span.data["http"]["path_tpl"] == "/response_headers"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200

        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert "X-Capture-This-Too" in asgi_span.data["http"]["header"]
        assert asgi_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in asgi_span.data["http"]["header"]
        assert asgi_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

    def test_non_async_simple(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/non_async_simple", headers=headers)

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi" and span.p == test_span.s  # noqa: E731
        asgi_span1 = get_first_span_by_filter(spans, span_filter)
        assert asgi_span1

        span_filter = lambda span: span.n == "asgi" and span.p == asgi_span1.s  # noqa: E731
        asgi_span2 = get_first_span_by_filter(spans, span_filter)
        assert asgi_span2

        # Same traceId
        traceId = test_span.t
        assert asgi_span1.t == traceId
        assert asgi_span2.t == traceId

        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span1.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span1.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span1.t)}"

        assert not asgi_span1.ec
        assert asgi_span1.data["http"]["host"] == "testserver"
        assert asgi_span1.data["http"]["path"] == "/non_async_simple"
        assert asgi_span1.data["http"]["path_tpl"] == "/non_async_simple"
        assert asgi_span1.data["http"]["method"] == "GET"
        assert asgi_span1.data["http"]["status"] == 200
        assert not asgi_span1.data["http"]["error"]
        assert not asgi_span1.data["http"]["params"]

        assert not asgi_span2.ec
        assert asgi_span2.data["http"]["host"], "testserver"
        assert asgi_span2.data["http"]["path"], "/users/1"
        assert asgi_span2.data["http"]["path_tpl"], "/users/{user_id}"
        assert asgi_span2.data["http"]["method"], "GET"
        assert asgi_span2.data["http"]["status"], 200
        assert not asgi_span2.data["http"]["error"]
        assert not asgi_span2.data["http"]["params"]

    def test_non_async_threadpool(self) -> None:
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/non_async_threadpool", headers=headers)

        assert result
        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        spans = self.recorder.queued_spans()
        # TODO: after support httpx, the expected value will be 3.
        assert len(spans) == 2

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert test_span.t == asgi_span.t
        assert test_span.s == asgi_span.p
        
        assert result.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert result.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert result.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "testserver"
        assert asgi_span.data["http"]["path"] == "/non_async_threadpool"
        assert asgi_span.data["http"]["path_tpl"] == "/non_async_threadpool"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200

        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]
