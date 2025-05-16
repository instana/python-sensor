# (c) Copyright IBM Corp. 2025
from typing import TYPE_CHECKING, Any, Dict, Optional

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

    # Assisted by watsonx Code Assistant
    def extract_carrier_headers(self, carrier: CarrierT) -> Dict[str, Any]:
        """
        Extracts headers from a carrier object.

        Args:
            carrier (CarrierT): The carrier object to extract headers from.

        Returns:
            Dict[str, Any]: A dictionary containing the extracted headers.
        """
        dc = {}
        try:
            if isinstance(carrier, list):
                for header in carrier:
                    if isinstance(header, tuple):
                        dc[header[0]] = header[1]
                    elif isinstance(header, dict):
                        for k, v in header.items():
                            dc[k] = v
            else:
                dc = self.extract_headers_dict(carrier)
        except Exception:
            logger.debug(
                f"kafka_propagator extract_headers_list: Couldn't convert - {carrier}"
            )

        return dc

    def extract(
        self, carrier: CarrierT, disable_w3c_trace_context: bool = False
    ) -> Optional["SpanContext"]:
        """
        This method overrides one of the Base classes as with the introduction
        of W3C trace context for the Kafka requests more extracting steps and
        logic was required.

        Args:
            carrier (CarrierT): The carrier object to extract headers from.
            disable_w3c_trace_context (bool): A flag to disable the W3C trace context.

        Returns:
            Optional["SpanContext"]: The extracted span context or None.
        """
        try:
            headers = self.extract_carrier_headers(carrier=carrier)
            return super(KafkaPropagator, self).extract(
                carrier=headers,
                disable_w3c_trace_context=disable_w3c_trace_context,
            )

        except Exception as e:
            logger.debug(f"kafka_propagator extract error: {e}", exc_info=True)

    # Assisted by watsonx Code Assistant
    def inject(
        self,
        span_context: "SpanContext",
        carrier: CarrierT,
        disable_w3c_trace_context: bool = True,
    ) -> None:
        """
        Inject the trace context into a carrier.

        Args:
            span_context (SpanContext): The SpanContext object containing trace information.
            carrier (CarrierT): The carrier object to store the trace context.
            disable_w3c_trace_context (bool, optional): A boolean flag to disable W3C trace context. Defaults to True.

        Returns:
            None
        """
        trace_id = span_context.trace_id
        span_id = span_context.span_id
        dictionary_carrier = self.extract_carrier_headers(carrier)

        suppression_level = 1
        if dictionary_carrier:
            # Suppression `level` made in the child context or in the parent context
            # has priority over any non-suppressed `level` setting
            suppression_level = int(self.extract_instana_headers(dictionary_carrier)[2])
            span_context.level = min(suppression_level, span_context.level)

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
            inject_key_value(
                carrier,
                self.KAFKA_HEADER_KEY_L_S,
                str(suppression_level).encode("utf-8"),
            )
            if suppression_level == 1:
                inject_key_value(
                    carrier,
                    self.KAFKA_HEADER_KEY_T,
                    hex_id_limited(trace_id).encode("utf-8"),
                )
                inject_key_value(
                    carrier,
                    self.KAFKA_HEADER_KEY_S,
                    format_span_id(span_id).encode("utf-8"),
                )
        except Exception:
            logger.debug("KafkaPropagator - inject error:", exc_info=True)
