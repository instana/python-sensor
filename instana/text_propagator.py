from __future__ import absolute_import

import opentracing as ot
from basictracer.context import SpanContext
from instana import util, log

prefix_tracer_state = 'X-INSTANA-'
prefix_baggage = 'X-INSTANA-BAGGAGE-'
field_name_trace_id = prefix_tracer_state + 'T'
field_name_span_id = prefix_tracer_state + 'S'


class TextPropagator():
    """
    A Propagator for TEXT_MAP.
    """

    def inject(self, span_context, carrier):
        try:
            carrier[field_name_trace_id] = '{0:x}'.format(span_context.trace_id)
            carrier[field_name_span_id] = '{0:x}'.format(span_context.span_id)
            if span_context.baggage is not None:
                for k in span_context.baggage:
                    carrier[prefix_baggage+k] = span_context.baggage[k]
        except Exception as e:
            log.debug("inject error: ", str(e))

    def extract(self, carrier):  # noqa
        try:
            if type(carrier) is dict or hasattr(carrier, "__dict__"):
                dc = carrier
            elif type(carrier) is list:
                dc = dict(carrier)
            else:
                raise ot.SpanContextCorruptedException()

            if field_name_trace_id in dc and field_name_span_id in dc:
                trace_id = util.header_to_id(dc[field_name_trace_id])
                span_id = util.header_to_id(dc[field_name_span_id])

            return SpanContext(span_id=span_id,
                               trace_id=trace_id,
                               baggage={},
                               sampled=True)

        except Exception as e:
            log.debug("extract error: ", str(e))
            return SpanContext()
