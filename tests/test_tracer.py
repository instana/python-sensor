# (c) Copyright IBM Corp. 2024

import pytest
from instana.agent.test import TestAgent
from instana.recorder import StanRecorder
from instana.sampling import InstanaSampler
from instana.span.span import InstanaSpan
from instana.span_context import SpanContext
from instana.tracer import InstanaTracer, InstanaTracerProvider
from opentelemetry.trace.span import _SPAN_ID_MAX_VALUE, INVALID_SPAN_ID


def test_tracer_defaults(tracer_provider: InstanaTracerProvider) -> None:
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )

    assert isinstance(tracer._sampler, InstanaSampler)
    assert isinstance(tracer.span_processor, StanRecorder)
    assert isinstance(tracer.exporter, TestAgent)
    assert len(tracer._propagators) == 3


def test_tracer_start_span(
    tracer_provider: InstanaTracerProvider, span_context: SpanContext
) -> None:
    span_name = "test-span"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    span = tracer.start_span(name=span_name, span_context=span_context)

    assert span
    assert isinstance(span, InstanaSpan)
    assert span.name == span_name
    assert not span.stack


def test_tracer_start_span_with_stack(tracer_provider: InstanaTracerProvider) -> None:
    span_name = "log"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
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


def test_tracer_start_span_Exception(
    mocker, tracer_provider: InstanaTracerProvider, span_context: SpanContext
) -> None:
    span_name = "test-span"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )

    mocker.patch(
        "instana.tracer.InstanaTracer._create_span_context",
        return_value={"key": "value"},
    )
    with pytest.raises(AttributeError):
        tracer.start_span(name=span_name, span_context=span_context)


def test_tracer_start_as_current_span(tracer_provider: InstanaTracerProvider) -> None:
    span_name = "test-span"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    with tracer.start_as_current_span(name=span_name) as span:
        assert span is not None
        assert isinstance(span, InstanaSpan)
        assert span.name == span_name


def test_tracer_create_span_context(
    span_context: SpanContext, tracer_provider: InstanaTracerProvider
) -> None:
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    new_span_context = tracer._create_span_context(span_context)

    assert span_context.trace_id == new_span_context.trace_id
    assert span_context.span_id != new_span_context.span_id
    assert span_context.long_trace_id == new_span_context.long_trace_id


def test_tracer_add_stack_high_limit(
    span: InstanaSpan, tracer_provider: InstanaTracerProvider
) -> None:
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    tracer._add_stack(span, 50)

    assert span.stack
    assert 40 >= len(span.stack)

    stack_0 = span.stack[0]
    assert 3 == len(stack_0)
    assert "c" in stack_0.keys()
    assert "n" in stack_0.keys()
    assert "m" in stack_0.keys()


def test_tracer_add_stack_low_limit(
    span: InstanaSpan, tracer_provider: InstanaTracerProvider
) -> None:
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    tracer._add_stack(span, 5)

    assert span.stack
    assert 5 >= len(span.stack)

    stack_0 = span.stack[0]
    assert 3 == len(stack_0)
    assert "c" in stack_0.keys()
    assert "n" in stack_0.keys()
    assert "m" in stack_0.keys()
