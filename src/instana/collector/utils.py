# (c) Copyright IBM Corp. 2024

from typing import TYPE_CHECKING, Type, List

from opentelemetry.trace.span import format_span_id
from opentelemetry.trace import SpanKind

from instana.util.ids import hex_id
if TYPE_CHECKING:
    from instana.span.base_span import BaseSpan


def format_span(
    queued_spans: List[Type["BaseSpan"]],
) -> List[Type["BaseSpan"]]:
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
        span.lt = hex_id(span.lt) if hasattr(span, "lt") else None
        if isinstance(span.k, SpanKind):
            span.k = span.k.value if not span.k is SpanKind.INTERNAL else 3
        spans.append(span)
    return spans
