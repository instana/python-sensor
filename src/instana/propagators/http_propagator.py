# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


from instana.log import logger
from instana.propagators.base_propagator import BasePropagator
from instana.util.ids import define_server_timing, hex_id_limited

from opentelemetry.trace.span import format_span_id

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
        dictionary_carrier = self.extract_headers_dict(carrier)
        if dictionary_carrier:
            # Suppression `level` made in the child context or in the parent context
            # has priority over any non-suppressed `level` setting
            child_level = int(self.extract_instana_headers(dictionary_carrier)[2] or "1")
            span_context.level = min(child_level, span_context.level)

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

            inject_key_value(carrier, self.HEADER_KEY_T, hex_id_limited(trace_id))
            inject_key_value(carrier, self.HEADER_KEY_S, format_span_id(span_id))
            inject_key_value(
                carrier, self.HEADER_KEY_SERVER_TIMING, define_server_timing(trace_id)
            )

        except Exception:
            logger.debug("inject error:", exc_info=True)
