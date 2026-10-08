# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import sys
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from instana.singletons import get_tracer
from instana.util.ids import hex_id
from tests.helpers import get_first_span_by_filter, get_spans_by_filter


def _assert_fastapi_otel_spans(
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
class TestFastAPIMiddleware:
    """
    Tests FastAPI with provided Middleware.
    """

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # We are using the TestClient from FastAPI to make it easier.
        from tests.apps.fastapi_app.app2 import fastapi_server

        self.client = TestClient(fastapi_server)
        # Clear all spans before a test run.
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        yield
        del fastapi_server

    def test_vanilla_get(self) -> None:
        result = self.client.get("/")

        assert result
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
        _assert_fastapi_otel_spans(spans, "/")

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
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert asgi_span.data["http"]["host"] == "testserver"
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]
        _assert_fastapi_otel_spans(spans, "/")
