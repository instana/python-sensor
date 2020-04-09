from __future__ import absolute_import

import opentracing as ot

from .log import logger
from .util import header_to_id
from .span import SpanContext


class BinaryPropagator():
    """
    A Propagator for TEXT_MAP.
    """
    HEADER_KEY_T = b'x-instana-t'
    HEADER_KEY_S = b'x-instana-s'
    HEADER_KEY_L = b'x-instana-l'

    def inject(self, span_context, carrier):
        try:
            trace_id = str.encode(span_context.trace_id)
            span_id = str.encode(span_context.span_id)
            level = str.encode("1")

            if type(carrier) is dict or hasattr(carrier, "__dict__"):
                carrier[self.HEADER_KEY_T] = trace_id
                carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = level
            elif type(carrier) is list:
                carrier.append((self.HEADER_KEY_T, trace_id))
                carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, level))
            elif type(carrier) is tuple:
                carrier = carrier.__add__(((self.HEADER_KEY_T, trace_id),))
                carrier = carrier.__add__(((self.HEADER_KEY_S, span_id),))
                carrier = carrier.__add__(((self.HEADER_KEY_L, level),))
            elif hasattr(carrier, '__setitem__'):
                carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, level)
            else:
                raise Exception("Unsupported carrier type", type(carrier))

            return carrier
        except Exception:
            logger.debug("inject error:", exc_info=True)

    def extract(self, carrier):  # noqa
        trace_id = None
        span_id = None
        level = None

        try:
            if type(carrier) is dict or hasattr(carrier, "__getitem__"):
                dc = carrier
            elif hasattr(carrier, "__dict__"):
                dc = carrier.__dict__
            elif type(carrier) is list:
                dc = dict(carrier)
            else:
                raise ot.SpanContextCorruptedException()

            for key, value in dc.items():
                if type(key) is str:
                    key = str.encode(key)

                if self.HEADER_KEY_T == key:
                    trace_id = header_to_id(value)
                elif self.HEADER_KEY_S == key:
                    span_id = header_to_id(value)
                elif self.HEADER_KEY_L == key:
                    level = value

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
