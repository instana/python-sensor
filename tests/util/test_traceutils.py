# (c) Copyright IBM Corp. 2024, 2025


from collections.abc import Generator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, use_span

from instana.singletons import agent, get_tracer
from instana.util.traceutils import extract_custom_headers, get_tracer_tuple


class TestTraceutils:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.tracer = get_tracer()

    @pytest.mark.parametrize(
        "custom_headers, format",
        [
            (
                {
                    "X-Capture-This-Too": "this too",
                    "X-Capture-That-Too": "that too",
                },
                False,
            ),
            (
                {
                    "HTTP_X_CAPTURE_THIS_TOO": "this too",
                    "HTTP_X_CAPTURE_THAT_TOO": "that too",
                },
                True,
            ),
            (
                [
                    ("X-CAPTURE-THIS-TOO", "this too"),
                    ("x-capture-that-too", "that too"),
                ],
                False,
            ),
            (
                [
                    (b"X-Capture-This-Too", b"this too"),
                    (b"X-Capture-That-Too", b"that too"),
                ],
                False,
            ),
            (
                [
                    ("HTTP_X_CAPTURE_THIS_TOO", "this too"),
                    ("HTTP_X_CAPTURE_THAT_TOO", "that too"),
                ],
                True,
            ),
        ],
    )
    def test_extract_custom_headers(self, span, custom_headers, format) -> None:
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]
        extract_custom_headers(span, custom_headers, format=format)
        assert len(span.attributes) == 2
        assert span.attributes["http.header.X-Capture-This-Too"] == "this too"
        assert span.attributes["http.header.X-Capture-That-Too"] == "that too"

    def test_get_tracer_tuple(self) -> None:
        response = get_tracer_tuple()
        assert response == (None, None, None)

        agent.options.allow_exit_as_root = True
        response = get_tracer_tuple()
        assert response == (self.tracer, None, None)
        agent.options.allow_exit_as_root = False

        with self.tracer.start_as_current_span("test") as span:
            response = get_tracer_tuple()
            assert response == (self.tracer, span, span.name)

    def test_get_tracer_tuple_with_non_instana_recording_span(self) -> None:
        """Non-Instana recording spans must still allow exit spans to be created.

        Regression guard for 010be7b6: the isinstance(current_span, InstanaSpan)
        guard introduced in that commit caused get_tracer_tuple() to return
        (None, None, None) whenever a third-party library's OTel span was active,
        silently dropping all httpx exit spans underneath it.
        """
        otel_tracer = TracerProvider().get_tracer("test-third-party")
        with otel_tracer.start_as_current_span("third-party-span") as otel_span:
            assert otel_span.is_recording()
            tracer, parent_span, span_name = get_tracer_tuple()
            # tracer must be returned so httpx instrumentation can open an exit span
            assert tracer is not None, (
                "get_tracer_tuple() must return a tracer when a non-Instana "
                "recording span is active — regression of 010be7b6"
            )
            # parent_span is None because we cannot safely type it as InstanaSpan
            assert parent_span is None
            assert span_name is None

    def test_get_tracer_tuple_no_span_no_exit_as_root(self) -> None:
        """No tracer is returned without an active span and allow_exit_as_root=False."""
        response = get_tracer_tuple()
        assert response == (None, None, None)

    def test_get_tracer_tuple_non_recording_span_returns_none(self) -> None:
        """A non-recording OTel span must not cause a tracer to be returned.

        Only recording spans are valid parents.
        """
        ctx = SpanContext(
            trace_id=0x000000000000000000000000DEADBEF0,
            span_id=0x00F067AA0BA902B7,
            is_remote=True,
            trace_flags=TraceFlags(0x00),  # sampled=False → not recording
        )
        non_recording = NonRecordingSpan(ctx)
        with use_span(non_recording, end_on_exit=False):
            tracer, parent_span, span_name = get_tracer_tuple()
            assert tracer is None
            assert parent_span is None
            assert span_name is None
