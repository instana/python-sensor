# (c) Copyright IBM Corp. 2024

from typing import TYPE_CHECKING, List

from opentelemetry.trace.span import format_span_id
from opentelemetry.trace import SpanKind

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan


def format_span(
    queued_spans: List["InstanaSpan"],
) -> List["InstanaSpan"]:
    """
    Format Span Kind and the Trace, Parent Span and Span IDs of the Spans to be a 64-bit
    Hexadecimal String instead of Integer before being pushed to a
    Collector (or Instana Agent).
    """
    spans = []
    for span in queued_spans:
        span.t = format_span_id(span.t)
        span.s = format_span_id(span.s)
        span.p = format_span_id(span.p) if span.p else None
        if isinstance(span.k, SpanKind):
            span.k = span.k.value if not span.k is SpanKind.INTERNAL else 3
        spans.append(span)
    return spans
