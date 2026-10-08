# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import sys
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from instana.singletons import agent, get_tracer
from instana.util.ids import hex_id
from tests.apps.fastapi_app.app import fastapi_server
from tests.helpers import get_first_span_by_filter, get_spans_by_filter


def assert_fastapi_otel_spans(
    spans: list,
    http_route: str,
    *,
    expect_serialization: bool = True,
    http_status_code: int = 200,
) -> None:
    """Assert the OTel spans emitted by FastAPI >= 0.115.0.

    FastAPI registers itself against the global OTel TracerProvider (which
    Instana provides), so every request produces extra sdk spans that land in
    Instana's recorder.

    Per request FastAPI emits:
      - fastapi.dependencies  (always)
      - fastapi.endpoint      (always)
      - fastapi.serialization (only on non-exception responses)
      - GET /path             (always, but orphan: p == 0)

    Args:
        spans: full list returned by recorder.queued_spans()
        http_route: the OTel http.route value, e.g. "/" or "/users/{user_id}"
        expect_serialization: False for exception responses (4xx/5xx via HTTPException
            or Response() objects that bypass JSON serialization)
        http_status_code: expected http.response.status_code on the HTTP entry span
    """
    otel_sdk_spans = get_spans_by_filter(
        spans,
        lambda s: s.n == "sdk" and s.data["sdk"]["name"].startswith("fastapi."),
    )
    otel_names = {s.data["sdk"]["name"] for s in otel_sdk_spans}
    assert "fastapi.dependencies" in otel_names
    assert "fastapi.endpoint" in otel_names
    if expect_serialization:
        assert "fastapi.serialization" in otel_names
    else:
        assert "fastapi.serialization" not in otel_names

    http_entry_span = get_first_span_by_filter(
        spans,
        lambda s: s.n == "sdk" and s.data["sdk"]["name"] == f"GET {http_route}",
    )
    assert http_entry_span, f"FastAPI HTTP entry span 'GET {http_route}' not found"
    assert http_entry_span.p == 0, "FastAPI HTTP entry span must be orphan (p == 0)"
    tags = http_entry_span.data["sdk"]["custom"]["tags"]
    assert tags["http.request.method"] == "GET"
    assert tags["http.route"] == http_route
    assert tags["http.response.status_code"] == http_status_code


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="FastAPI >= 0.115.0 (required for OTel span assertions) only supports Python 3.10+",
)
class TestFastAPI:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # We are using the TestClient from Starlette/FastAPI to make it easier.
        self.client = TestClient(fastapi_server)

        # Clear all spans before a test run
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
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

        # FastAPI >= 0.115.0 emits 4 extra OTel spans per request via the global
        # OTel provider that Instana registers: fastapi.dependencies,
        # fastapi.endpoint, fastapi.serialization, GET /
        assert len(spans) == 5
        span_filter = lambda span: span.n == "asgi"  # noqa: E731
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        assert_fastapi_otel_spans(spans, "/")

    def test_basic_get(self) -> None:
        result = None
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 4 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, fastapi.serialization, GET /
        # TODO: after support httpx, the expected value will be 7.
        assert len(spans) == 6

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

        assert_fastapi_otel_spans(spans, "/")

    def test_400(self) -> None:
        result = None
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 3 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, GET /400 (orphan).
        # fastapi.serialization is absent on exception responses.
        # TODO: after support httpx, the expected value will be 6.
        assert len(spans) == 5

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

        assert_fastapi_otel_spans(
            spans, "/400", expect_serialization=False, http_status_code=400
        )

    def test_500(self) -> None:
        result = None
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 3 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, GET /500 (orphan).
        # fastapi.serialization is absent on exception responses.
        # TODO: after support httpx, the expected value will be 6.
        assert len(spans) == 5

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

        assert_fastapi_otel_spans(
            spans, "/500", expect_serialization=False, http_status_code=500
        )
        # error.type is set by FastAPI on 5xx responses
        http_entry_span = get_first_span_by_filter(
            spans,
            lambda s: s.n == "sdk" and s.data["sdk"]["name"] == "GET /500",
        )
        assert "error.type" in http_entry_span.data["sdk"]["custom"]["tags"]

    def test_path_templates(self) -> None:
        result = None
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 4 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, fastapi.serialization, GET /users/{user_id}
        # TODO: after support httpx, the expected value will be 7.
        assert len(spans) == 6

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

        assert_fastapi_otel_spans(spans, "/users/{user_id}")
        # url.path carries the resolved path (with actual param value)
        http_entry_span = get_first_span_by_filter(
            spans,
            lambda s: s.n == "sdk" and s.data["sdk"]["name"] == "GET /users/{user_id}",
        )
        assert http_entry_span.data["sdk"]["custom"]["tags"]["url.path"] == "/users/1"

    def test_secret_scrubbing(self) -> None:
        result = None
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 4 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, fastapi.serialization, GET /
        # TODO: after support httpx, the expected value will be 7.
        assert len(spans) == 6

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

        assert_fastapi_otel_spans(spans, "/")

    def test_synthetic_request(self) -> None:
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 4 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, fastapi.serialization, GET /
        # TODO: after support httpx, the expected value will be 7.
        assert len(spans) == 6

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

        assert_fastapi_otel_spans(spans, "/")

    def test_request_header_capture(self) -> None:
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 4 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, fastapi.serialization, GET /
        # TODO: after support httpx, the expected value will be 7.
        assert len(spans) == 6

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

        assert_fastapi_otel_spans(spans, "/")

    def test_response_header_capture(self) -> None:
        # The background FastAPI server is pre-configured with custom headers
        # to capture.

        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 3 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, GET /response_headers (orphan).
        # fastapi.serialization is absent — Response() objects bypass JSON serialization.
        # TODO: after support httpx, the expected value will be 6.
        assert len(spans) == 5

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

        # Response() objects bypass FastAPI's JSON serialization pipeline
        assert_fastapi_otel_spans(
            spans, "/response_headers", expect_serialization=False
        )

    def test_non_async_simple(self) -> None:
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 4 extra OTel spans per request (8 total for 2 requests):
        # fastapi.dependencies, fastapi.endpoint, GET /..., and one internal span each.
        assert len(spans) == 11

        span_filter = (  # noqa: E731
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "asgi" and span.p == test_span.s  # noqa: E731
        asgi_span1 = get_first_span_by_filter(spans, span_filter)
        assert asgi_span1

        # asgi_span2 is a child of the fastapi.endpoint span which is itself a
        # child of asgi_span1; find it by excluding the first asgi span.
        span_filter = lambda span: span.n == "asgi" and span.s != asgi_span1.s  # noqa: E731
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
        with self.tracer.start_as_current_span("test") as span:
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
        # FastAPI >= 0.115.0 adds 4 extra OTel spans per request:
        # fastapi.dependencies, fastapi.endpoint, GET /non_async_threadpool, and one internal span.
        # TODO: after support httpx, the expected value will be 7.
        assert len(spans) == 6

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
