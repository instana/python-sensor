# (c) Copyright IBM Corp. 2024

from typing import TYPE_CHECKING, List

from opentelemetry.trace.span import format_span_id

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan


def format_trace_and_span_ids(
    queued_spans: List["InstanaSpan"],
) -> List["InstanaSpan"]:
    """
    Format the Trace, Parent Span, and Span IDs of Spans to be a 64-bit
    Hexadecimal String instead of Integer before being pushed to a
    Collector (or Instana Agent).
    """
    spans = []
    for span in queued_spans:
        span.t = format_span_id(span.t)
        span.s = format_span_id(span.s)
        span.p = format_span_id(span.p) if span.p else None
        spans.append(span)
    return spans
