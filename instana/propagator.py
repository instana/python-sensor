from __future__ import absolute_import
import opentracing as ot
from instana import util

prefix_tracer_state = 'HTTP_X_INSTANA_'
field_name_trace_id = prefix_tracer_state + 'T'
field_name_span_id = prefix_tracer_state + 'S'
field_count = 2


class HTTPPropagator():
    """A Propagator for Format.HTTP_HEADERS. """

    def inject(self, span_context, carrier):
        carrier[field_name_trace_id] = util.id_to_header(span_context.trace_id)
        carrier[field_name_span_id] = util.id_to_header(span_context.span_id)

    def extract(self, carrier):  # noqa
        count = 0
        span_id, trace_id = (0, 0)
        for k in carrier:
            v = carrier[k]
            k = k.lower()
            if k == field_name_span_id:
                span_id = util.header_to_id(v)
                count += 1
            elif k == field_name_trace_id:
                trace_id = util.header_to_id(v)
                count += 1

        if count != field_count:
            raise ot.SpanContextCorruptedException()

        return ot.SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            baggage={},
            sampled=True)
