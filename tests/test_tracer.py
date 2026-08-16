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


# ---------------------------------------------------------------------------
# _ensure_instana_span_context tests
# ---------------------------------------------------------------------------


def _make_tracer(tracer_provider: InstanaTracerProvider) -> InstanaTracer:
    return InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )


def test_ensure_instana_span_context_none(
    tracer_provider: InstanaTracerProvider,
) -> None:
    """None input returns None — new root span will be created."""
    tracer = _make_tracer(tracer_provider)
    assert tracer._ensure_instana_span_context(None) is None


def test_ensure_instana_span_context_invalid(
    tracer_provider: InstanaTracerProvider,
) -> None:
    """An invalid OTel SpanContext (trace_id=0) returns None."""
    from opentelemetry.trace import INVALID_SPAN_CONTEXT

    tracer = _make_tracer(tracer_provider)
    assert tracer._ensure_instana_span_context(INVALID_SPAN_CONTEXT) is None


def test_ensure_instana_span_context_passthrough(
    tracer_provider: InstanaTracerProvider,
    span_context: SpanContext,
) -> None:
    """An existing Instana SpanContext is returned unchanged."""
    tracer = _make_tracer(tracer_provider)
    result = tracer._ensure_instana_span_context(span_context)
    assert result is span_context


def test_ensure_instana_span_context_wraps_foreign_otel_context(
    tracer_provider: InstanaTracerProvider,
) -> None:
    """A plain OTel SpanContext (e.g. from Phoenix) is wrapped into an Instana SpanContext
    while preserving trace_id and span_id so the distributed-trace chain is not broken."""
    from opentelemetry.trace import SpanContext as OtelSpanContext, TraceFlags

    foreign = OtelSpanContext(
        trace_id=0xAAAABBBBCCCCDDDDEEEEFFFF00001111,
        span_id=0x1234567890ABCDEF,
        is_remote=True,
        trace_flags=TraceFlags(1),
    )
    tracer = _make_tracer(tracer_provider)
    result = tracer._ensure_instana_span_context(foreign)

    assert isinstance(result, SpanContext)
    assert result.trace_id == foreign.trace_id
    assert result.span_id == foreign.span_id
    assert result.is_remote == foreign.is_remote
    assert result.trace_flags == foreign.trace_flags


def test_start_span_with_foreign_otel_context_does_not_raise(
    tracer_provider: InstanaTracerProvider,
) -> None:
    """start_span must not raise TypeError when the active span comes from
    a third-party OTel provider (Phoenix, OpenTelemetry SDK, etc.)."""
    from opentelemetry import context as otel_context
    from opentelemetry.trace import (
        NonRecordingSpan,
        SpanContext as OtelSpanContext,
        TraceFlags,
        set_span_in_context,
    )

    foreign_span_ctx = OtelSpanContext(
        trace_id=0xAAAABBBBCCCCDDDDEEEEFFFF00001111,
        span_id=0x1234567890ABCDEF,
        is_remote=True,
        trace_flags=TraceFlags(1),
    )
    foreign_span = NonRecordingSpan(foreign_span_ctx)
    ctx = set_span_in_context(foreign_span)
    token = otel_context.attach(ctx)

    tracer = _make_tracer(tracer_provider)
    try:
        span = tracer.start_span(name="test-with-foreign-context")
        assert isinstance(span, InstanaSpan)
        # trace_id must be inherited from the foreign provider's span
        assert span.context.trace_id == foreign_span_ctx.trace_id
    finally:
        otel_context.detach(token)


def test_start_span_with_invalid_foreign_context_creates_root_span(
    tracer_provider: InstanaTracerProvider,
) -> None:
    """When the active foreign span carries an INVALID SpanContext, Instana
    starts a new root span (trace_id == span_id) rather than raising."""
    from opentelemetry import context as otel_context
    from opentelemetry.trace import (
        INVALID_SPAN_CONTEXT,
        NonRecordingSpan,
        set_span_in_context,
    )

    foreign_span = NonRecordingSpan(INVALID_SPAN_CONTEXT)
    ctx = set_span_in_context(foreign_span)
    token = otel_context.attach(ctx)

    tracer = _make_tracer(tracer_provider)
    try:
        span = tracer.start_span(name="test-root-from-invalid-foreign")
        assert isinstance(span, InstanaSpan)
        assert span.context.trace_id == span.context.span_id  # root span
    finally:
        otel_context.detach(token)
