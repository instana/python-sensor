from __future__ import absolute_import

import opentracing as ot
from basictracer.context import SpanContext

from .log import logger
from .util import header_to_id

# The carrier can be a dict or a list.
# Using the trace header as an example, it can be in the following forms
# for extraction:
#   X-Instana-T
#   HTTP_X_INSTANA_T
#
# The second form above is found in places like Django middleware for
# incoming requests.
#
# For injection, we only support the standard format:
#   X-Instana-T


class HTTPPropagator():
    """A Propagator for Format.HTTP_HEADERS. """

    HEADER_KEY_T = 'X-Instana-T'
    HEADER_KEY_S = 'X-Instana-S'
    HEADER_KEY_L = 'X-Instana-L'
    LC_HEADER_KEY_T = 'x-instana-t'
    LC_HEADER_KEY_S = 'x-instana-s'
    LC_HEADER_KEY_L = 'x-instana-l'

    ALT_HEADER_KEY_T = 'HTTP_X_INSTANA_T'
    ALT_HEADER_KEY_S = 'HTTP_X_INSTANA_S'
    ALT_HEADER_KEY_L = 'HTTP_X_INSTANA_L'
    ALT_LC_HEADER_KEY_T = 'http_x_instana_t'
    ALT_LC_HEADER_KEY_S = 'http_x_instana_s'
    ALT_LC_HEADER_KEY_L = 'http_x_instana_l'

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

            # Headers can exist in the standard X-Instana-T/S format or the alternate HTTP_X_INSTANA_T/S style
            # We do a case insensitive search to cover all possible variations of incoming headers.
            for key in dc.keys():
                lc_key = key.lower()

                if self.LC_HEADER_KEY_T == lc_key:
                    trace_id = header_to_id(dc[key])
                elif self.LC_HEADER_KEY_S == lc_key:
                    span_id = header_to_id(dc[key])

                elif self.ALT_LC_HEADER_KEY_T == lc_key:
                    trace_id = header_to_id(dc[key])
                elif self.ALT_LC_HEADER_KEY_S == lc_key:
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
