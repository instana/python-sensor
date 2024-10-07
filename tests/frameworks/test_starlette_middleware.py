# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from typing import Generator

import pytest
from instana.singletons import agent, tracer
from starlette.testclient import TestClient

from instana.util.ids import hex_id
from tests.apps.starlette_app.app2 import starlette_server
from tests.helpers import get_first_span_by_filter


class TestStarletteMiddleware:
    """
    Tests Starlette with provided Middleware.
    """

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # We are using the TestClient from Starlette to make it easier.
        self.client = TestClient(starlette_server)
        # Clear all spans before a test run.
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        yield

    def test_vanilla_get(self) -> None:
        result = self.client.get("/")

        assert result
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert "Server-Timing" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"

        # Starlette instrumentation (like all instrumentation) _always_ traces
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
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert asgi_span.data["http"]["host"] == "testserver"
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_basic_get_500(self) -> None:
        result = None
        with tracer.start_as_current_span("test") as span:
            # As TestClient() is based on httpx, and we don't support it yet,
            # we must pass the SDK trace_id and span_id to the ASGI server.
            span_context = span.get_span_context()
            headers = {
                "X-INSTANA-T": hex_id(span_context.trace_id),
                "X-INSTANA-S": hex_id(span_context.span_id),
            }
            result = self.client.get("/five", headers=headers)

        assert result
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
        assert asgi_span.data["http"]["path"] == "/five"
        assert asgi_span.data["http"]["path_tpl"] == "/five"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 500
        assert asgi_span.data["http"]["host"] == "testserver"
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]
