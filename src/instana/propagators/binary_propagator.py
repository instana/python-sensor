# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


from typing import Optional

from opentelemetry.trace.span import format_span_id

from instana.log import logger
from instana.propagators.base_propagator import BasePropagator, CarrierT
from instana.span_context import SpanContext
from instana.util.ids import define_server_timing


class BinaryPropagator(BasePropagator):
    """
    A Propagator for BINARY.
    The BINARY format represents SpanContexts in an opaque bytearray carrier.
    """

    # ByteArray variations from base class
    HEADER_KEY_T = b"x-instana-t"
    HEADER_KEY_S = b"x-instana-s"
    HEADER_KEY_L = b"x-instana-l"
    HEADER_SERVER_TIMING = b"server-timing"
    HEADER_KEY_TRACEPARENT = b"traceparent"
    HEADER_KEY_TRACESTATE = b"tracestate"

    def __init__(self) -> None:
        super(BinaryPropagator, self).__init__()

    def inject(
        self,
        span_context: SpanContext,
        carrier: CarrierT,
        disable_w3c_trace_context: bool = True,
    ) -> Optional[CarrierT]:
        try:
            trace_id = format_span_id(span_context.trace_id).encode()
            span_id = format_span_id(span_context.span_id).encode()
            level = str(span_context.level).encode()
            server_timing = (
                None
                if self.is_server_timing_disabled()
                else define_server_timing(span_context.trace_id).encode()
            )

            if disable_w3c_trace_context:
                traceparent, tracestate = [None] * 2
            else:
                traceparent, tracestate = self._get_participating_trace_context(
                    span_context
                )
                try:
                    traceparent = str.encode(traceparent)  # type: ignore[arg-type]
                    tracestate = str.encode(tracestate)  # type: ignore[arg-type]
                except Exception:
                    traceparent, tracestate = [None] * 2

            headers = []
            if traceparent and tracestate:
                headers.append((self.HEADER_KEY_TRACEPARENT, traceparent))
                headers.append((self.HEADER_KEY_TRACESTATE, tracestate))
            headers.append((self.HEADER_KEY_T, trace_id))
            headers.append((self.HEADER_KEY_S, span_id))
            headers.append((self.HEADER_KEY_L, level))
            if server_timing:
                headers.append((self.HEADER_SERVER_TIMING, server_timing))

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                for key, value in headers:
                    carrier[key] = value  # type: ignore[index]
            elif isinstance(carrier, list):
                carrier.extend(headers)
            elif isinstance(carrier, tuple):
                carrier = carrier.__add__(tuple(headers))
            elif hasattr(carrier, "__setitem__"):
                for key, value in headers:
                    carrier.__setitem__(key, value)
            else:
                raise Exception("Unsupported carrier type", type(carrier))

            return carrier
        except Exception:
            logger.debug("inject error:", exc_info=True)
