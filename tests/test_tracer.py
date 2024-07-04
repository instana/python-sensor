# (c) Copyright IBM Corp. 2024

from opentelemetry.trace import set_span_in_context
from opentelemetry.trace.span import _SPAN_ID_MAX_VALUE, INVALID_SPAN_ID
import pytest

from instana.span import InstanaSpan
from instana.span_context import SpanContext
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

def test_tracer_start_span(span) -> None:
    span_name = "test-span"
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )
    parent_context = set_span_in_context(span)
    span = tracer.start_span(name=span_name, context=parent_context)

    assert span
    assert isinstance(span, InstanaSpan)
    assert span.name == span_name
    assert not span.stack


def test_tracer_start_span_with_stack(span: InstanaSpan) -> None:
    span_name = "log"
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )
    span = tracer.start_span(name=span_name)

    assert span
    assert isinstance(span, InstanaSpan)
    assert span.name == span_name
    assert span.stack

    stack_0 = span.stack[0]
    assert 3 == len(stack_0)
    assert "c" in stack_0.keys()
    assert "n" in stack_0.keys()
    assert "m" in stack_0.keys()


def test_tracer_start_span_Exception(mocker, span) -> None:
    span_name = "test-span"
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )

    parent_context = set_span_in_context(span)

    mocker.patch("instana.span.InstanaSpan.get_span_context", return_value={"key": "value"})
    with pytest.raises(TypeError):
        tracer.start_span(name=span_name, context=parent_context)


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


def test_tracer_create_span_context(span_context: SpanContext) -> None:
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )
    new_span_context = tracer._create_span_context(span_context)

    assert span_context.trace_id == new_span_context.trace_id
    assert span_context.span_id != new_span_context.span_id
    assert span_context.long_trace_id == new_span_context.long_trace_id


def test_tracer_add_stack_high_limit(span: InstanaSpan) -> None:
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )
    tracer._add_stack(span, 50)

    assert span.stack
    assert 40 >= len(span.stack)

    stack_0 = span.stack[0]
    assert 3 == len(stack_0)
    assert "c" in stack_0.keys()
    assert "n" in stack_0.keys()
    assert "m" in stack_0.keys()


def test_tracer_add_stack_low_limit(span: InstanaSpan) -> None:
    provider = InstanaTracerProvider()
    tracer = InstanaTracer(
        provider.sampler,
        provider.recorder,
        provider._span_processor,
        provider._propagators,
    )
    tracer._add_stack(span, 5)

    assert span.stack
    assert 5 >= len(span.stack)

    stack_0 = span.stack[0]
    assert 3 == len(stack_0)
    assert "c" in stack_0.keys()
    assert "n" in stack_0.keys()
    assert "m" in stack_0.keys()
