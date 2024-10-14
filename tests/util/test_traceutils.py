# (c) Copyright IBM Corp. 2024

from unittest.mock import patch

from instana.singletons import agent, tracer
from instana.tracer import InstanaTracer
from instana.util.traceutils import (
    extract_custom_headers,
    get_active_tracer,
    get_tracer_tuple,
    tracing_is_off,
)


def test_extract_custom_headers(span) -> None:
    agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]
    request_headers = {
        "X-Capture-This-Too": "this too",
        "X-Capture-That-Too": "that too",
    }
    extract_custom_headers(span, request_headers)
    assert len(span.attributes) == 2
    assert span.attributes["http.header.X-Capture-This-Too"] == "this too"
    assert span.attributes["http.header.X-Capture-That-Too"] == "that too"


def test_get_activate_tracer() -> None:
    assert not get_active_tracer()

    with tracer.start_as_current_span("test"):
        response = get_active_tracer()
        assert isinstance(response, InstanaTracer)
        assert response == tracer
        with patch("instana.span.span.InstanaSpan.is_recording", return_value=False):
            assert not get_active_tracer()


def test_get_tracer_tuple() -> None:
    response = get_tracer_tuple()
    assert response == (None, None, None)

    agent.options.allow_exit_as_root = True
    response = get_tracer_tuple()
    assert response == (tracer, None, None)
    agent.options.allow_exit_as_root = False

    with tracer.start_as_current_span("test") as span:
        response = get_tracer_tuple()
        assert response == (tracer, span, span.name)


def test_tracing_is_off() -> None:
    response = tracing_is_off()
    assert response
    with tracer.start_as_current_span("test"):
        response = tracing_is_off()
        assert not response

    agent.options.allow_exit_as_root = True
    response = tracing_is_off()
    assert not response
    agent.options.allow_exit_as_root = False
