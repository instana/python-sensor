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
            if disable_w3c_trace_context:
                traceparent, tracestate = [None] * 2
            else:
                traceparent, tracestate = self._get_participating_trace_context(span_context)

            level = span_context.level

            if level not in ('0', 0):
                trace_id = span_context.trace_id
                span_id = span_context.span_id

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                if traceparent:
                    carrier[self.HEADER_KEY_TRACEPARENT] = traceparent
                if tracestate:
                    carrier[self.HEADER_KEY_TRACESTATE] = tracestate
                if level not in ('0', 0):
                    carrier[self.HEADER_KEY_T] = trace_id
                    carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = str(level)
            elif isinstance(carrier, list):
                if traceparent:
                    carrier.append((self.HEADER_KEY_TRACEPARENT, traceparent))
                if tracestate:
                    carrier.append((self.HEADER_KEY_TRACESTATE, tracestate))
                if level not in ('0', 0):
                    carrier.append((self.HEADER_KEY_T, trace_id))
                    carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, str(level)))
            elif hasattr(carrier, '__setitem__'):
                if traceparent:
                    carrier.__setitem__(self.HEADER_KEY_TRACEPARENT, traceparent)
                if tracestate:
                    carrier.__setitem__(self.HEADER_KEY_TRACESTATE, tracestate)
                if level not in ('0', 0):
                    carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                    carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, str(level))
            else:
                raise Exception("Unsupported carrier type", type(carrier))

        except Exception:
            logger.debug("inject error:", exc_info=True)
