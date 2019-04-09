from __future__ import absolute_import

import opentracing as ot
from basictracer.context import SpanContext

from .log import logger
from .util import header_to_id


class TextPropagator():
    """
    A Propagator for TEXT_MAP.
    """

    HEADER_KEY_T = 'X-INSTANA-T'
    HEADER_KEY_S = 'X-INSTANA-S'
    HEADER_KEY_L = 'X-INSTANA-L'

    def inject(self, span_context, carrier):
        try:
            trace_id = span_context.trace_id
            span_id = span_context.span_id

            if type(carrier) is dict or hasattr(carrier, "__dict__"):
                carrier[self.HEADER_KEY_T] = trace_id
                carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = "1"
            elif type(carrier) is list:
                carrier.append((self.HEADER_KEY_T, trace_id))
                carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, "1"))
            elif hasattr(carrier, '__setitem__'):
                carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, "1")
            else:
                raise Exception("Unsupported carrier type", type(carrier))

        except:
            logger.debug("inject error:", exc_info=True)

    def extract(self, carrier):  # noqa
        trace_id = None
        span_id = None

        try:
            if type(carrier) is dict or hasattr(carrier, "__getitem__"):
                dc = carrier
            elif hasattr(carrier, "__dict__"):
                dc = carrier.__dict__
            elif type(carrier) is list:
                dc = dict(carrier)
            else:
                raise ot.SpanContextCorruptedException()

            for key in dc.keys():
                if self.HEADER_KEY_T == key:
                    trace_id = header_to_id(dc[key])
                elif self.HEADER_KEY_S == key:
                    span_id = header_to_id(dc[key])

            ctx = None
            if trace_id is not None and span_id is not None:
                ctx = SpanContext(span_id=span_id,
                                  trace_id=trace_id,
                                  baggage={},
                                  sampled=True)
            return ctx

        except Exception as e:
            logger.debug("extract error:", exc_info=True)
