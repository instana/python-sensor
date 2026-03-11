# (c) Copyright IBM Corp. 2024

import pytest
from opentelemetry.context.context import Context
from opentelemetry.trace import set_span_in_context
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




# OpenTelemetry Compliance Tests for context parameter

def test_tracer_start_span_with_context_parameter(
    tracer_provider: InstanaTracerProvider, span: InstanaSpan, context: Context
) -> None:
    """Test start_span() with context parameter (OpenTelemetry-compliant usage)."""
    span_name = "test-span-with-context"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Start a span with context parameter
    new_span = tracer.start_span(name=span_name, context=context)
    
    assert new_span
    assert isinstance(new_span, InstanaSpan)
    assert new_span.name == span_name
    # Verify the span has the correct parent from the context
    assert new_span.parent_id == span.context.span_id


def test_tracer_start_span_with_span_context_parameter(
    tracer_provider: InstanaTracerProvider, span_context: SpanContext
) -> None:
    """Test start_span() with span_context parameter (backward compatibility)."""
    span_name = "test-span-with-span-context"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Start a span with span_context parameter (existing behavior)
    new_span = tracer.start_span(name=span_name, span_context=span_context)
    
    assert new_span
    assert isinstance(new_span, InstanaSpan)
    assert new_span.name == span_name
    assert new_span.parent_id == span_context.span_id


def test_tracer_start_span_with_both_parameters(
    tracer_provider: InstanaTracerProvider, 
    span_context: SpanContext,
    context: Context
) -> None:
    """Test start_span() with both context and span_context (span_context takes precedence)."""
    span_name = "test-span-both-params"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # When both are provided, span_context should take precedence
    new_span = tracer.start_span(
        name=span_name, 
        context=context, 
        span_context=span_context
    )
    
    assert new_span
    assert isinstance(new_span, InstanaSpan)
    assert new_span.name == span_name
    # Should use span_context, not the one from context
    assert new_span.parent_id == span_context.span_id


def test_tracer_start_span_with_neither_parameter(
    tracer_provider: InstanaTracerProvider
) -> None:
    """Test start_span() with neither parameter (uses current span context)."""
    span_name = "test-span-no-params"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Start a span without any context parameters
    new_span = tracer.start_span(name=span_name)
    
    assert new_span
    assert isinstance(new_span, InstanaSpan)
    assert new_span.name == span_name
    # Should be a root span since no parent context is provided
    # In Instana, root spans have parent_id=0 (INVALID_SPAN_ID)
    assert new_span.parent_id == 0


def test_tracer_start_span_context_extraction(
    tracer_provider: InstanaTracerProvider, 
    span: InstanaSpan,
    context: Context
) -> None:
    """Test that span_context is correctly extracted from context parameter."""
    span_name = "test-span-context-extraction"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Start a span with context parameter
    new_span = tracer.start_span(name=span_name, context=context)
    
    # Verify the extracted span_context matches the span in the context
    assert new_span.parent_id == span.context.span_id
    assert new_span.context.trace_id == span.context.trace_id


def test_tracer_start_as_current_span_with_context_parameter(
    tracer_provider: InstanaTracerProvider, 
    span: InstanaSpan,
    context: Context
) -> None:
    """Test start_as_current_span() with context parameter (OpenTelemetry-compliant usage)."""
    span_name = "test-current-span-with-context"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Use context manager with context parameter
    with tracer.start_as_current_span(name=span_name, context=context) as new_span:
        assert new_span is not None
        assert isinstance(new_span, InstanaSpan)
        assert new_span.name == span_name
        assert new_span.parent_id == span.context.span_id
        assert get_current_span() is new_span


def test_tracer_start_as_current_span_with_span_context_parameter(
    tracer_provider: InstanaTracerProvider, span_context: SpanContext
) -> None:
    """Test start_as_current_span() with span_context parameter (backward compatibility)."""
    span_name = "test-current-span-with-span-context"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Use context manager with span_context parameter
    with tracer.start_as_current_span(
        name=span_name, span_context=span_context
    ) as new_span:
        assert new_span is not None
        assert isinstance(new_span, InstanaSpan)
        assert new_span.name == span_name
        assert new_span.parent_id == span_context.span_id


def test_tracer_start_as_current_span_with_both_parameters(
    tracer_provider: InstanaTracerProvider,
    span_context: SpanContext,
    context: Context
) -> None:
    """Test start_as_current_span() with both parameters (span_context takes precedence)."""
    span_name = "test-current-span-both-params"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # When both are provided, span_context should take precedence
    with tracer.start_as_current_span(
        name=span_name, context=context, span_context=span_context
    ) as new_span:
        assert new_span is not None
        assert isinstance(new_span, InstanaSpan)
        assert new_span.name == span_name
        # Should use span_context, not the one from context
        assert new_span.parent_id == span_context.span_id


def test_tracer_start_as_current_span_with_neither_parameter(
    tracer_provider: InstanaTracerProvider
) -> None:
    """Test start_as_current_span() with neither parameter (uses current span context)."""
    span_name = "test-current-span-no-params"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Use context manager without any context parameters
    with tracer.start_as_current_span(name=span_name) as new_span:
        assert new_span is not None
        assert isinstance(new_span, InstanaSpan)
        assert new_span.name == span_name
        # Should be a root span since no parent context is provided
        # In Instana, root spans have parent_id=0 (INVALID_SPAN_ID)
        assert new_span.parent_id == 0


def test_tracer_start_as_current_span_context_manager_works(
    tracer_provider: InstanaTracerProvider
) -> None:
    """Test that the context manager properly sets and unsets the current span."""
    span_name = "test-context-manager"
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Before entering context manager
    initial_span = get_current_span()
    
    with tracer.start_as_current_span(name=span_name) as new_span:
        # Inside context manager, new_span should be current
        assert get_current_span() is new_span
        assert new_span.end_time is None
    
    # After exiting context manager, span should be ended
    assert new_span.end_time is not None
    # Current span should be restored (or INVALID_SPAN if no parent)
    assert get_current_span() is initial_span or get_current_span() is INVALID_SPAN


def test_tracer_minimal_example_from_bug_report(
    tracer_provider: InstanaTracerProvider
) -> None:
    """Test the minimal example from BUG_REPORT.md that previously caused TypeError."""
    # This is the exact code from the bug report that should now work
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # This should not raise TypeError anymore
    with tracer.start_as_current_span("test-span", context=None):
        pass
    
    # Test also works with start_span
    span = tracer.start_span("test-span", context=None)
    assert span is not None
    assert isinstance(span, InstanaSpan)


def test_tracer_context_none_vs_not_provided(
    tracer_provider: InstanaTracerProvider
) -> None:
    """Test that context=None behaves the same as not providing context parameter."""
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    # Create span with context=None
    span1 = tracer.start_span("span1", context=None)
    
    # Create span without context parameter
    span2 = tracer.start_span("span2")
    
    # Both should be root spans with no parent
    # In Instana, root spans have parent_id=0 (INVALID_SPAN_ID)
    assert span1.parent_id == 0
    assert span2.parent_id == 0
    
    # Both should have valid span contexts
    assert span1.context.is_valid
    assert span2.context.is_valid


def test_tracer_nested_spans_with_context_parameter(
    tracer_provider: InstanaTracerProvider
) -> None:
    """Test nested spans using context parameter."""
    tracer = InstanaTracer(
        tracer_provider.sampler,
        tracer_provider._span_processor,
        tracer_provider._exporter,
        tracer_provider._propagators,
    )
    
    parent_span_name = "parent-span-context"
    child_span_name = "child-span-context"
    
    with tracer.start_as_current_span(name=parent_span_name) as parent_span:
        # Get the context with the parent span
        parent_context = set_span_in_context(parent_span)
        
        # Create child span using context parameter
        with tracer.start_as_current_span(
            name=child_span_name, context=parent_context
        ) as child_span:
            assert get_current_span() is child_span
            assert child_span.parent_id == parent_span.context.span_id
            assert child_span.context.trace_id == parent_span.context.trace_id
        
        # After child exits, parent should be current again
        assert get_current_span() is parent_span
