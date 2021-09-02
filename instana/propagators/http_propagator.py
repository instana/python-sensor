# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

from instana.log import logger
from instana.propagators.base_propagator import BasePropagator


class HTTPPropagator(BasePropagator):
    """
    Instana Propagator for Format.HTTP_HEADERS.

    The HTTP_HEADERS format deals with key-values with string to string mapping.
    The character set should be restricted to HTTP compatible.
    """

    def __init__(self):
        super(HTTPPropagator, self).__init__()

    def inject(self, span_context, carrier, disable_w3c_trace_context=False):
        try:
            trace_id = span_context.trace_id
            span_id = span_context.span_id
            level = span_context.level

            if disable_w3c_trace_context:
                traceparent, tracestate = [None] * 2
            else:
                traceparent, tracestate = self._get_participating_trace_context(span_context)

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                if traceparent and tracestate:
                    carrier[self.HEADER_KEY_TRACEPARENT] = traceparent
                    carrier[self.HEADER_KEY_TRACESTATE] = tracestate
                carrier[self.HEADER_KEY_T] = trace_id
                carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = "1"
            elif isinstance(carrier, list):
                if traceparent and tracestate:
                    carrier.append((self.HEADER_KEY_TRACEPARENT, traceparent))
                    carrier.append((self.HEADER_KEY_TRACESTATE, tracestate))
                carrier.append((self.HEADER_KEY_T, trace_id))
                carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, "1"))
            elif hasattr(carrier, '__setitem__'):
                if traceparent and tracestate:
                    carrier.__setitem__(self.HEADER_KEY_TRACEPARENT, traceparent)
                    carrier.__setitem__(self.HEADER_KEY_TRACESTATE, tracestate)
                carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, "1")
            else:
                raise Exception("Unsupported carrier type", type(carrier))

        except Exception:
            logger.debug("inject error:", exc_info=True)










