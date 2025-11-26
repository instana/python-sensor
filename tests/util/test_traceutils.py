# (c) Copyright IBM Corp. 2024


from typing import Generator
import pytest

from instana.singletons import agent, get_tracer
from instana.util.traceutils import (
    extract_custom_headers,
    get_tracer_tuple,
)


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
