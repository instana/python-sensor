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
        trace_id = span_context.trace_id
        span_id = span_context.span_id
        serializable_level = str(span_context.level)

        if disable_w3c_trace_context:
            traceparent, tracestate = [None] * 2
        else:
            traceparent, tracestate = self._get_participating_trace_context(span_context)

        def inject_key_value(carrier, key, value):
            if isinstance(carrier, list):
                carrier.append((key, value))
            elif isinstance(carrier, dict) or '__setitem__' in dir(carrier):
                carrier[key] = value
            else:
                raise Exception("Unsupported carrier type", type(carrier))

        try:
            inject_key_value(carrier, self.HEADER_KEY_L, serializable_level)

            if traceparent:
                inject_key_value(carrier, self.HEADER_KEY_TRACEPARENT, traceparent)
            if tracestate:
                inject_key_value(carrier, self.HEADER_KEY_TRACESTATE, tracestate)

            if span_context.suppression:
                return

            inject_key_value(carrier, self.HEADER_KEY_T, trace_id)
            inject_key_value(carrier, self.HEADER_KEY_S, span_id)

        except Exception:
            logger.debug("inject error:", exc_info=True)
