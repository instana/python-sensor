# (c) Copyright IBM Corp. 2024

import pytest
from opentelemetry.context.context import Context
from opentelemetry.trace import SpanKind, TraceFlags
from opentelemetry.trace import SpanContext as OtelSpanContext
from opentelemetry.trace import set_span_in_context
from opentelemetry.trace.span import (
    DEFAULT_TRACE_OPTIONS,
    DEFAULT_TRACE_STATE,
    NonRecordingSpan,
    _SPAN_ID_MAX_VALUE,
)

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
# Parametrized tests: start_span with different context / parent-span types
# ---------------------------------------------------------------------------

# A valid OTel-native trace_id and span_id (not Instana SpanContext subclass)
_OTEL_TRACE_ID = 0x000000000000000018BED7B8D2E72F6B
_OTEL_SPAN_ID = 0x5FB3484FB90A5BAD


def _make_otel_context(trace_id: int, span_id: int, is_valid: bool = True) -> Context:
    """Return an OTel Context carrying a NonRecordingSpan with a plain OtelSpanContext."""
    if is_valid:
        sc = OtelSpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=True,
            trace_flags=DEFAULT_TRACE_OPTIONS,
            trace_state=DEFAULT_TRACE_STATE,
        )
    else:
        # OTel INVALID_SPAN_CONTEXT has trace_id=0 and span_id=0 → is_valid == False
        sc = OtelSpanContext(
            trace_id=0,
            span_id=0,
            is_remote=False,
        )
    return set_span_in_context(NonRecordingSpan(sc))


def _make_instana_context(trace_id: int, span_id: int) -> Context:
    """Return a Context carrying a NonRecordingSpan with an Instana SpanContext."""
    sc = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
    )
    return set_span_in_context(NonRecordingSpan(sc))


@pytest.mark.parametrize(
    "context_factory, expected_trace_id, is_root, converts_to_instana, has_trace_parent",
    [
        # --- Instana SpanContext parent (valid) ---
        # The tracer must inherit the trace_id and create a new child span_id.
        pytest.param(
            lambda: _make_instana_context(_OTEL_TRACE_ID, _OTEL_SPAN_ID),
            _OTEL_TRACE_ID,
            False,   # NOT a root span – parent_id must be set
            False,   # Already an InstanaSpanContext, no conversion
            None,    # trace_parent field is None (plain Instana parent)
            id="instana_span_context_parent",
        ),
        # --- OTel SpanContext parent (valid) ---
        # The tracer must convert it to an Instana SpanContext and use its trace_id.
        pytest.param(
            lambda: _make_otel_context(_OTEL_TRACE_ID, _OTEL_SPAN_ID, is_valid=True),
            _OTEL_TRACE_ID,
            False,   # NOT a root span – parent_id must be set
            True,    # Conversion happens → child SpanContext.trace_parent == True
            True,    # trace_parent flag must be True after conversion
            id="otel_span_context_valid_parent",
        ),
        # --- OTel SpanContext parent (invalid, i.e. trace_id=0, span_id=0) ---
        # The tracer must ignore it and create a new root span.
        pytest.param(
            lambda: _make_otel_context(0, 0, is_valid=False),
            None,    # trace_id is generated fresh – we only check it is > 0
            True,    # IS a root span – no parent
            False,   # No conversion (invalid context is discarded)
            None,    # no trace_parent on a fresh root
            id="otel_span_context_invalid_parent",
        ),
        # --- No context (None) ---
        # The tracer must create a standalone root span.
        pytest.param(
            lambda: None,
            None,    # trace_id is generated fresh – we only check it is > 0
            True,    # IS a root span – no parent
            False,   # No conversion needed
            None,    # no trace_parent on a fresh root
            id="no_context_root_span",
        ),
    ],
)
def test_tracer_start_span_with_context_types(
    tracer_provider: InstanaTracerProvider,
    context_factory,
    expected_trace_id,
    is_root: bool,
    converts_to_instana: bool,
    has_trace_parent,
) -> None:
    """Test start_span behaviour for all relevant parent-context scenarios.

    Covers:
    * Instana SpanContext as parent  → trace_id inherited, new span_id, no conversion
    * Valid OTel SpanContext parent  → converted to InstanaSpanContext, trace_parent=True
    * Invalid OTel SpanContext       → discarded, new root span created
    * No context (None)              → new root span created
    """
    span_name = "test-span-context-type"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    ctx = context_factory()
    span = tracer.start_span(name=span_name, context=ctx)

    assert isinstance(span, InstanaSpan)
    assert span.name == span_name

    sc = span.context
    assert isinstance(sc, SpanContext), "InstanaTracer must always produce an Instana SpanContext"

    # --- trace_id checks ---
    if expected_trace_id is not None:
        assert sc.trace_id == expected_trace_id, (
            f"Expected trace_id {expected_trace_id:#x}, got {sc.trace_id:#x}"
        )
    else:
        # Fresh root span: trace_id must be a newly generated valid value
        assert sc.trace_id > INVALID_SPAN_ID
        assert sc.trace_id <= _SPAN_ID_MAX_VALUE

    # --- span_id must always be a fresh, valid value ---
    assert sc.span_id > INVALID_SPAN_ID
    assert sc.span_id <= _SPAN_ID_MAX_VALUE

    # --- parent / root relationship ---
    if is_root:
        # When no valid parent is present, parent_id is either None or the
        # INVALID_SPAN_ID (0) – both indicate "no real parent".
        assert not span.parent_id, (
            f"Root span must have no real parent_id, got {span.parent_id!r}"
        )
        # For genuine root spans trace_id == span_id (Instana convention)
        if expected_trace_id is None:
            assert sc.trace_id == sc.span_id, (
                "Root span must have trace_id == span_id"
            )
    else:
        assert span.parent_id == _OTEL_SPAN_ID, (
            "Child span must carry the parent's span_id as parent_id"
        )
        assert sc.span_id != _OTEL_SPAN_ID, "Child must get a new span_id"

    # --- OTel-to-Instana conversion flag ---
    if converts_to_instana:
        assert sc.trace_parent is True, (
            "SpanContext created from OTel parent must have trace_parent=True"
        )
    elif has_trace_parent is None:
        assert sc.trace_parent is None, (
            "Non-converted SpanContext must not have trace_parent set"
        )
