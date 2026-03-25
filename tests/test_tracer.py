# (c) Copyright IBM Corp. 2024

import pytest
from opentelemetry.context.context import Context
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import _SPAN_ID_MAX_VALUE

from instana.agent.host import HostAgent
from instana.recorder import StanRecorder
from instana.sampling import InstanaSampler
from instana.span.span import (
    INVALID_SPAN,
    INVALID_SPAN_ID,
    InstanaSpan,
    get_current_span,
)
from instana.span_context import SpanContext
from instana.tracer import InstanaTracer, InstanaTracerProvider


def test_tracer_defaults(tracer_provider: InstanaTracerProvider) -> None:
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )

    assert isinstance(tracer._sampler, InstanaSampler)
    assert isinstance(tracer.span_processor, StanRecorder)
    assert isinstance(tracer.exporter, HostAgent)
    assert len(tracer._propagators) == 4


def test_tracer_start_span(
    tracer_provider: InstanaTracerProvider, context: Context
) -> None:
    span_name = "test-span"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    span = tracer.start_span(name=span_name, context=context)

    assert span
    assert isinstance(span, InstanaSpan)
    assert span.name == span_name
    assert not span.stack


def test_tracer_start_span_Exception(
    mocker, tracer_provider: InstanaTracerProvider, context: Context
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
        tracer.start_span(name=span_name, context=context)


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


def test_tracer_nested_span(tracer_provider: InstanaTracerProvider) -> None:
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    parent_span_name = "parent-span"
    child_span_name = "child-span"
    with tracer.start_as_current_span(name=parent_span_name) as pspan:
        assert get_current_span() is pspan
        with tracer.start_as_current_span(name=child_span_name) as cspan:
            assert get_current_span() is cspan
            assert cspan.parent_id == pspan.context.span_id
        # child span goes out of scope
        assert cspan.end_time is not None
        assert get_current_span() is pspan
    # parent span goes out of scope
    assert pspan.end_time is not None
    assert get_current_span() is INVALID_SPAN


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

    assert span_context.trace_id > INVALID_SPAN_ID
    assert span_context.trace_id <= _SPAN_ID_MAX_VALUE

    assert span_context.span_id > INVALID_SPAN_ID
    assert span_context.span_id <= _SPAN_ID_MAX_VALUE


def test_tracer_create_span_context_root(
    tracer_provider: InstanaTracerProvider,
) -> None:
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    new_span_context = tracer._create_span_context(parent_context=None)

    assert new_span_context.trace_id > INVALID_SPAN_ID
    assert new_span_context.trace_id <= _SPAN_ID_MAX_VALUE

    assert new_span_context.trace_id == new_span_context.span_id


@pytest.mark.parametrize(
    "kind",
    [
        SpanKind.INTERNAL,
        SpanKind.SERVER,
        SpanKind.CLIENT,
        SpanKind.PRODUCER,
        SpanKind.CONSUMER,
    ],
)
def test_tracer_start_span_with_kind(
    tracer_provider: InstanaTracerProvider, context: Context, kind: SpanKind
) -> None:
    """Test that tracer.start_span correctly passes kind parameter to InstanaSpan."""
    span_name = f"test-span-{kind.name.lower()}"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    span = tracer.start_span(name=span_name, context=context, kind=kind)

    assert span
    assert isinstance(span, InstanaSpan)
    assert span.name == span_name
    assert span.kind == kind


def test_tracer_start_span_default_kind(
    tracer_provider: InstanaTracerProvider, context: Context
) -> None:
    """Test that tracer.start_span defaults to SpanKind.INTERNAL when kind is not specified."""
    span_name = "test-span-default-kind"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    span = tracer.start_span(name=span_name, context=context)

    assert span
    assert isinstance(span, InstanaSpan)
    assert span.kind == SpanKind.INTERNAL


def test_tracer_start_as_current_span_with_kind(
    tracer_provider: InstanaTracerProvider,
) -> None:
    """Test that tracer.start_as_current_span correctly passes kind parameter."""
    span_name = "test-span-context-manager"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    with tracer.start_as_current_span(name=span_name, kind=SpanKind.SERVER) as span:
        assert span is not None
        assert isinstance(span, InstanaSpan)
        assert span.name == span_name
        assert span.kind == SpanKind.SERVER


def test_tracer_nested_span_with_different_kinds(
    tracer_provider: InstanaTracerProvider,
) -> None:
    """Test that nested spans can have different kind values."""
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    parent_span_name = "parent-server-span"
    child_span_name = "child-client-span"

    with tracer.start_as_current_span(
        name=parent_span_name, kind=SpanKind.SERVER
    ) as pspan:
        assert pspan.kind == SpanKind.SERVER

        with tracer.start_as_current_span(
            name=child_span_name, kind=SpanKind.CLIENT
        ) as cspan:
            assert cspan.kind == SpanKind.CLIENT
            assert cspan.parent_id == pspan.context.span_id
            # Verify kinds are independent
            assert pspan.kind == SpanKind.SERVER
            assert cspan.kind == SpanKind.CLIENT


def test_tracer_kind_propagation_to_readable_span(
    tracer_provider: InstanaTracerProvider, context: Context
) -> None:
    """Test that kind is properly propagated when span is converted to ReadableSpan."""
    span_name = "test-span-readable"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    span = tracer.start_span(name=span_name, context=context, kind=SpanKind.PRODUCER)

    assert span.kind == SpanKind.PRODUCER

    # Create readable span (this happens internally when span.end() is called)
    readable_span = span._readable_span()

    assert readable_span.kind == SpanKind.PRODUCER
