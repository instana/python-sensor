# (c) Copyright IBM Corp. 2025
from typing import TYPE_CHECKING

from opentelemetry.trace.span import format_span_id

from instana.log import logger
from instana.propagators.base_propagator import BasePropagator, CarrierT
from instana.util.ids import hex_id_limited

if TYPE_CHECKING:
    from instana.span_context import SpanContext


class KafkaPropagator(BasePropagator):
    """
    Instana Propagator for Format.KAFKA_HEADERS.

    The KAFKA_HEADERS format deals with key-values with string to string mapping.
    The character set should be restricted to HTTP compatible.
    """

    def __init__(self) -> None:
        super(KafkaPropagator, self).__init__()

    def inject(
        self,
        span_context: "SpanContext",
        carrier: CarrierT,
        disable_w3c_trace_context: bool = True,
    ) -> None:
        trace_id = span_context.trace_id
        span_id = span_context.span_id
        dictionary_carrier = self.extract_headers_dict(carrier)

        if dictionary_carrier:
            # Suppression `level` made in the child context or in the parent context
            # has priority over any non-suppressed `level` setting
            child_level = int(
                self.extract_instana_headers(dictionary_carrier)[2] or "1"
            )
            span_context.level = min(child_level, span_context.level)

        serializable_level = str(span_context.level)

        def inject_key_value(carrier, key, value):
            if isinstance(carrier, list):
                carrier.append((key, value))
            elif isinstance(carrier, dict) or "__setitem__" in dir(carrier):
                carrier[key] = value
            else:
                raise Exception(
                    f"KafkaPropagator: Unsupported carrier type {type(carrier)}",
                )

        try:
            inject_key_value(carrier, "X_INSTANA_L_S", serializable_level)
            inject_key_value(carrier, "X_INSTANA_T", hex_id_limited(trace_id))
            inject_key_value(carrier, "X_INSTANA_S", format_span_id(span_id))

        except Exception:
            logger.debug("KafkaPropagator - inject error:", exc_info=True)
