# (c) Copyright IBM Corp. 2024

import pickle
from opentelemetry.trace.span import (
    DEFAULT_TRACE_OPTIONS,
    DEFAULT_TRACE_STATE,
    format_span_id,
)

from instana.span_context import SpanContext
from instana.util.ids import generate_id


def test_span_context_defaults():
    trace_id = generate_id()
    span_id = generate_id()
    span_context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
    )

    assert isinstance(span_context, SpanContext)
    assert span_context.trace_id == trace_id
    assert span_context.span_id == span_id
    assert span_context.trace_id != span_context.span_id
    assert not span_context.is_remote
    assert span_context.trace_flags == DEFAULT_TRACE_OPTIONS
    assert span_context.trace_state == DEFAULT_TRACE_STATE
    assert span_context.is_valid
    assert span_context.level == 1
    assert not span_context.synthetic
    assert span_context.trace_parent is None
    assert span_context.instana_ancestor is None
    assert span_context.long_trace_id is None
    assert span_context.correlation_type is None
    assert span_context.correlation_id is None
    assert span_context.traceparent is None
    assert span_context.tracestate is None
    assert not span_context.suppression
    assert repr(span_context) == f"SpanContext(trace_id=0x{format_span_id(trace_id)}, span_id=0x{format_span_id(span_id)}, trace_flags=0x{DEFAULT_TRACE_OPTIONS:02x}, trace_state={DEFAULT_TRACE_STATE!r}, is_remote=False, synthetic=False)"


def test_span_context_invalid():
    span_context = SpanContext(
        trace_id=9999999999999999999999999999999999999999999999999999999999999999999999999999,
        span_id=9,
        is_remote=False,
    )
    assert not span_context.is_valid


def test_span_context_pickle():
    trace_id = generate_id()
    span_id = generate_id()
    span_context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
    )

    span_context_binary = pickle.dumps(span_context) 
    span_context_pickle = pickle.loads(span_context_binary)
    assert trace_id == span_context_pickle.trace_id
    assert span_id == span_context_pickle.span_id

