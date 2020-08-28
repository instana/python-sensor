from __future__ import absolute_import

import opentracing as ot

from .log import logger
from .util import header_to_id
from .span_context import SpanContext


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

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                carrier[self.HEADER_KEY_T] = trace_id
                carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = "1"
            elif isinstance(carrier, list):
                carrier.append((self.HEADER_KEY_T, trace_id))
                carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, "1"))
            elif isinstance(carrier, tuple):
                carrier = carrier.__add__(((self.HEADER_KEY_T, trace_id),))
                carrier = carrier.__add__(((self.HEADER_KEY_S, span_id),))
                carrier = carrier.__add__(((self.HEADER_KEY_L, "1"),))
            elif hasattr(carrier, '__setitem__'):
                carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, "1")
            else:
                raise Exception("Unsupported carrier type", type(carrier))

            return carrier
        except Exception:
            logger.debug("inject error:", exc_info=True)

    def extract(self, carrier):  # noqa
        trace_id = None
        span_id = None
        level = 1

        try:
            if isinstance(carrier, dict) or hasattr(carrier, "__getitem__"):
                dc = carrier
            elif hasattr(carrier, "__dict__"):
                dc = carrier.__dict__
            elif isinstance(carrier, list):
                dc = dict(carrier)
            else:
                raise ot.SpanContextCorruptedException()

            for key in dc.keys():
                if self.HEADER_KEY_T == key:
                    trace_id = header_to_id(dc[key])
                elif self.HEADER_KEY_S == key:
                    span_id = header_to_id(dc[key])
                elif self.HEADER_KEY_L == key:
                    level = dc[key]

            ctx = None
            if trace_id is not None and span_id is not None:
                ctx = SpanContext(span_id=span_id,
                                         trace_id=trace_id,
                                         level=level,
                                         baggage={},
                                         sampled=True)
            return ctx

        except Exception:
            logger.debug("extract error:", exc_info=True)
