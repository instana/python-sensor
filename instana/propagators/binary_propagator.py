# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

from ..log import logger
from .base_propagator import BasePropagator
from ..w3c_trace_context.traceparent import Traceparent
from ..w3c_trace_context.tracestate import Tracestate


class BinaryPropagator(BasePropagator):
    """
    A Propagator for BINARY.
    The BINARY format represents SpanContexts in an opaque bytearray carrier.
    """

    # ByteArray variations from base class
    HEADER_KEY_T = b'x-instana-t'
    HEADER_KEY_S = b'x-instana-s'
    HEADER_KEY_L = b'x-instana-l'
    HEADER_SERVER_TIMING = b'server-timing'
    HEADER_KEY_TRACEPARENT = b'traceparent'
    HEADER_KEY_TRACESTATE = b'tracestate'

    def __init__(self):
        self.__tp = Traceparent()
        self.__ts = Tracestate()
        super(BinaryPropagator, self).__init__()

    def inject(self, span_context, carrier, binary_w3c_injection=False):
        try:
            trace_id = str.encode(span_context.trace_id)
            span_id = str.encode(span_context.span_id)
            level = str.encode(str(span_context.level))
            server_timing = str.encode("intid;desc=%s" % span_context.trace_id)
            if binary_w3c_injection:
                traceparent = span_context.traceparent
                tracestate = span_context.tracestate
                traceparent = self.__tp.update_traceparent(traceparent, span_context.trace_id, span_context.span_id,
                                                           span_context.level)
                tracestate = self.__ts.update_tracestate(tracestate, span_context.trace_id, span_context.span_id)
                try:
                    traceparent = str.encode(traceparent)
                    tracestate = str.encode(tracestate)
                except Exception:
                    traceparent, tracestate = [None] * 2
            else:
                traceparent, tracestate = [None] * 2

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                if traceparent and tracestate:
                    carrier[self.HEADER_KEY_TRACEPARENT] = traceparent
                    carrier[self.HEADER_KEY_TRACESTATE] = tracestate
                carrier[self.HEADER_KEY_T] = trace_id
                carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = level
                carrier[self.HEADER_SERVER_TIMING] = server_timing
            elif isinstance(carrier, list):
                if traceparent and tracestate:
                    carrier.append((self.HEADER_KEY_TRACEPARENT, traceparent))
                    carrier.append((self.HEADER_KEY_TRACESTATE, tracestate))
                carrier.append((self.HEADER_KEY_T, trace_id))
                carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, level))
                carrier.append((self.HEADER_SERVER_TIMING, server_timing))
            elif isinstance(carrier, tuple):
                if traceparent and tracestate:
                    carrier.__add__(((self.HEADER_KEY_TRACEPARENT, traceparent),))
                    carrier.__add__(((self.HEADER_KEY_TRACESTATE, tracestate),))
                carrier = carrier.__add__(((self.HEADER_KEY_T, trace_id),))
                carrier = carrier.__add__(((self.HEADER_KEY_S, span_id),))
                carrier = carrier.__add__(((self.HEADER_KEY_L, level),))
                carrier = carrier.__add__(((self.HEADER_SERVER_TIMING, server_timing),))
            elif hasattr(carrier, '__setitem__'):
                if traceparent and tracestate:
                    carrier.__setitem__(self.HEADER_KEY_TRACEPARENT, traceparent)
                    carrier.__setitem__(self.HEADER_KEY_TRACESTATE, tracestate)
                carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, level)
                carrier.__setitem__(self.HEADER_SERVER_TIMING, server_timing)
            else:
                raise Exception("Unsupported carrier type", type(carrier))

            return carrier
        except Exception:
            logger.debug("inject error:", exc_info=True)
