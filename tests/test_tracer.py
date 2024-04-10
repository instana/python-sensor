# (c) Copyright IBM Corp. 2024

from opentelemetry.trace.span import _SPAN_ID_MAX_VALUE, INVALID_SPAN_ID

from instana.span import InstanaSpan
from instana.tracer import InstanaTracer, InstanaTracerProvider


def test_tracer_defaults() -> None:
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )

    assert tracer.tracer_id > INVALID_SPAN_ID
    assert tracer.tracer_id <= _SPAN_ID_MAX_VALUE
    assert tracer.recorder == provider.recorder
    assert tracer._sampler == provider.sampler
    assert tracer._span_processor == provider._span_processor
    assert tracer._propagators == provider._propagators

def test_tracer_start_span() -> None:
    span_name = "test-span"
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )
    span = tracer.start_span(name=span_name)

    assert span is not None
    assert isinstance(span, InstanaSpan)
    assert span.name == span_name

def test_tracer_start_as_current_span() -> None:
    span_name = "test-span"
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )
    with tracer.start_as_current_span(name=span_name) as span:
        assert span is not None
        assert isinstance(span, InstanaSpan)
        assert span.name == span_name
