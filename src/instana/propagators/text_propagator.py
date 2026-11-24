# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


from typing import Optional

from opentelemetry.trace.span import format_span_id

from instana.log import logger
from instana.propagators.base_propagator import BasePropagator, CarrierT
from instana.span_context import SpanContext
from instana.util.ids import define_server_timing


class TextPropagator(BasePropagator):
    """
    Instana context propagator for TEXT_MAP.

    The TEXT_MAP deals with key-values with string to string mapping.
    The character set is unrestricted.
    """

    def inject(
        self,
        span_context: SpanContext,
        carrier: CarrierT,
        disable_w3c_trace_context: bool = True,
    ) -> Optional[CarrierT]:
        try:
            trace_id = format_span_id(span_context.trace_id)
            span_id = format_span_id(span_context.span_id)
            server_timing = (
                None
                if self.is_server_timing_disabled()
                else define_server_timing(span_context.trace_id).encode()
            )

            headers = [
                (self.LC_HEADER_KEY_T, trace_id),
                (self.LC_HEADER_KEY_S, span_id),
                (self.LC_HEADER_KEY_L, "1"),
            ]
            if server_timing:
                headers.append((self.LC_HEADER_KEY_SERVER_TIMING, server_timing))

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
