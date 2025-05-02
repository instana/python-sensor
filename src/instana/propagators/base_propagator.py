# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import os

from typing import Any, Optional, TypeVar, Dict, List, Tuple

from instana.log import logger
from instana.span_context import SpanContext
from instana.util.ids import (
    header_to_id,
    header_to_long_id,
    hex_id,
    internal_id,
    internal_id_limited,
    hex_id_limited,
)
from instana.w3c_trace_context.traceparent import Traceparent
from instana.w3c_trace_context.tracestate import Tracestate

from opentelemetry.trace import (
    INVALID_SPAN_ID,
    INVALID_TRACE_ID,
)

# The carrier, typed here as CarrierT, can be a dict, a list, or a tuple.
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
CarrierT = TypeVar("CarrierT", Dict, List, Tuple)


class BasePropagator(object):
    HEADER_KEY_T = "X-INSTANA-T"
    HEADER_KEY_S = "X-INSTANA-S"
    HEADER_KEY_L = "X-INSTANA-L"
    HEADER_KEY_SYNTHETIC = "X-INSTANA-SYNTHETIC"
    HEADER_KEY_TRACEPARENT = "traceparent"
    HEADER_KEY_TRACESTATE = "tracestate"
    HEADER_KEY_SERVER_TIMING = "Server-Timing"

    LC_HEADER_KEY_T = "x-instana-t"
    LC_HEADER_KEY_S = "x-instana-s"
    LC_HEADER_KEY_L = "x-instana-l"
    LC_HEADER_KEY_SYNTHETIC = "x-instana-synthetic"
    LC_HEADER_KEY_SERVER_TIMING = "server-timing"

    ALT_LC_HEADER_KEY_T = "http_x_instana_t"
    ALT_LC_HEADER_KEY_S = "http_x_instana_s"
    ALT_LC_HEADER_KEY_L = "http_x_instana_l"
    ALT_LC_HEADER_KEY_SYNTHETIC = "http_x_instana_synthetic"
    ALT_HEADER_KEY_TRACEPARENT = "http_traceparent"
    ALT_HEADER_KEY_TRACESTATE = "http_tracestate"
    ALT_LC_HEADER_KEY_SERVER_TIMING = "http_server_timing"

    # ByteArray variations
    B_HEADER_KEY_T = b"x-instana-t"
    B_HEADER_KEY_S = b"x-instana-s"
    B_HEADER_KEY_L = b"x-instana-l"
    B_HEADER_KEY_SYNTHETIC = b"x-instana-synthetic"
    B_HEADER_KEY_TRACEPARENT = b"traceparent"
    B_HEADER_KEY_TRACESTATE = b"tracestate"
    B_HEADER_KEY_SERVER_TIMING = b"server-timing"

    B_ALT_LC_HEADER_KEY_T = b"http_x_instana_t"
    B_ALT_LC_HEADER_KEY_S = b"http_x_instana_s"
    B_ALT_LC_HEADER_KEY_L = b"http_x_instana_l"
    B_ALT_LC_HEADER_KEY_SYNTHETIC = b"http_x_instana_synthetic"
    B_ALT_HEADER_KEY_TRACEPARENT = b"http_traceparent"
    B_ALT_HEADER_KEY_TRACESTATE = b"http_tracestate"
    B_ALT_LC_HEADER_KEY_SERVER_TIMING = b"http_server_timing"

    # Kafka Modern Headers
    KAFKA_HEADER_KEY_T = "x_instana_t"
    KAFKA_HEADER_KEY_S = "x_instana_s"
    KAFKA_HEADER_KEY_L_S = "x_instana_l_s"

    def __init__(self):
        self._tp = Traceparent()
        self._ts = Tracestate()

    @staticmethod
    def extract_headers_dict(carrier: CarrierT) -> Optional[Dict]:
        """
        This method converts the incoming carrier into a dict.

        :param carrier: CarrierT
        :return: Dict | None
        """
        dc = None
        try:
            if isinstance(carrier, dict):
                dc = carrier
            elif hasattr(carrier, "__dict__"):
                dc = carrier.__dict__
                if not dc:
                    dc = dict(carrier)
            else:
                dc = dict(carrier)
        except Exception:
            logger.debug(
                f"base_propagator extract_headers_dict: Couldn't convert - {carrier}"
            )

        return dc

    @staticmethod
    def _get_ctx_level(level: str) -> int:
        """
        Extract the level value and return it, as it may include correlation values.

        :param level: str
        :return: int
        """
        try:
            ctx_level = int(level.split(",")[0]) if level else 1
        except Exception:
            ctx_level = 1
        return ctx_level

    @staticmethod
    def _get_correlation_properties(level: str):
        """
        Get the correlation values if they are present.

        :param level: str
        :return: Tuple[Any, Any] - correlation_type, correlation_id
        """
        correlation_type, correlation_id = [None] * 2
        try:
            correlation_type = (
                level.split(",")[1].split("correlationType=")[1].split(";")[0]
            )
            if "correlationId" in level:
                correlation_id = (
                    level.split(",")[1].split("correlationId=")[1].split(";")[0]
                )
        except Exception:
            logger.debug("extract instana correlation type/id error:", exc_info=True)

        return correlation_type, correlation_id

    def _get_participating_trace_context(self, span_context: SpanContext):
        """
        This method is called for getting the updated traceparent and tracestate values.

        :param span_context: SpanContext
        :return: traceparent, tracestate
        """
        if span_context.long_trace_id and not span_context.trace_parent:
            tp_trace_id = span_context.long_trace_id
        else:
            tp_trace_id = span_context.trace_id
        traceparent = span_context.traceparent
        tracestate = span_context.tracestate
        traceparent = self._tp.update_traceparent(
            traceparent, tp_trace_id, span_context.span_id, span_context.level
        )

        # In suppression mode do not update the tracestate and
        # do not add the 'in=' key-value pair to the incoming tracestate
        # Just propagate the incoming tracestate (if any) unchanged.
        if span_context.suppression:
            return traceparent, tracestate

        tracestate = self._ts.update_tracestate(
            tracestate,
            hex_id_limited(span_context.trace_id),
            hex_id(span_context.span_id),
        )
        return traceparent, tracestate

    def __determine_span_context(
        self,
        trace_id: int,
        span_id: int,
        level: str,
        synthetic: bool,
        traceparent,
        tracestate,
        disable_w3c_trace_context: bool,
    ) -> SpanContext:
        """
        This method determines the span context depending on a set of conditions being met
        Detailed description of the conditions can be found in the instana internal technical-documentation,
        under section http-processing-for-instana-tracers.

        :param trace_id: int - instana trace id
        :param span_id: int - instana span id
        :param level: str - instana level
        :param synthetic: bool - instana synthetic
        :param traceparent:
        :param tracestate:
        :param disable_w3c_trace_context: bool - flag used to enable w3c trace context only on HTTP requests
        :return: SpanContext
        """
        correlation = False
        disable_traceparent = os.environ.get(
            "INSTANA_DISABLE_W3C_TRACE_CORRELATION", ""
        )
        instana_ancestor = None

        if level and "correlationType" in level:
            trace_id, span_id = [None] * 2
            correlation = True

        (
            ctx_level,
            ctx_synthetic,
            ctx_trace_parent,
            ctx_instana_ancestor,
            ctx_long_trace_id,
            ctx_correlation_type,
            ctx_correlation_id,
            ctx_traceparent,
            ctx_tracestate,
        ) = [None] * 9

        ctx_level = self._get_ctx_level(level)
        ctx_trace_id = trace_id if ctx_level > 0 else None
        ctx_span_id = span_id if ctx_level > 0 else None

        if (
            trace_id
            and span_id
            and trace_id != INVALID_TRACE_ID
            and span_id != INVALID_SPAN_ID
        ):
            ctx_synthetic = synthetic

            hex_trace_id = hex_id(trace_id)
            if len(hex_trace_id) > 16:
                ctx_long_trace_id = hex_trace_id

        elif (
            not disable_w3c_trace_context
            and traceparent
            and not trace_id
            and not span_id
        ):
            _, tp_trace_id, tp_parent_id, _ = self._tp.get_traceparent_fields(
                traceparent
            )

            if tracestate and "in=" in tracestate:
                instana_ancestor = self._ts.get_instana_ancestor(tracestate)

            if disable_traceparent == "":
                ctx_trace_id = hex_id_limited(tp_trace_id)
                ctx_span_id = tp_parent_id
                ctx_synthetic = synthetic
                ctx_trace_parent = True
                ctx_instana_ancestor = instana_ancestor
                ctx_long_trace_id = tp_trace_id
            else:
                if instana_ancestor:
                    ctx_trace_id = instana_ancestor.t
                    ctx_span_id = instana_ancestor.p
                    ctx_synthetic = synthetic

        elif synthetic:
            ctx_synthetic = synthetic

        if correlation:
            ctx_correlation_type, ctx_correlation_id = self._get_correlation_properties(
                level
            )

        if traceparent:
            ctx_traceparent = traceparent
            ctx_tracestate = tracestate

        if ctx_trace_id:
            if isinstance(ctx_trace_id, int):
                # check if ctx_trace_id is a valid internal trace id
                if ctx_trace_id <= 2**64 - 1:
                    trace_id = ctx_trace_id
                else:
                    trace_id = internal_id(hex_id_limited(ctx_trace_id))
            else:
                trace_id = internal_id(ctx_trace_id)
        else:
            trace_id = INVALID_TRACE_ID

        return SpanContext(
            trace_id=trace_id,
            span_id=internal_id_limited(ctx_span_id)
            if ctx_span_id
            else INVALID_SPAN_ID,
            is_remote=False,
            level=ctx_level,
            synthetic=ctx_synthetic,
            trace_parent=ctx_trace_parent,
            instana_ancestor=ctx_instana_ancestor,
            long_trace_id=ctx_long_trace_id,
            correlation_type=ctx_correlation_type,
            correlation_id=ctx_correlation_id,
            traceparent=ctx_traceparent,
            tracestate=ctx_tracestate,
        )

    def extract_instana_headers(
        self, dc: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[int], Optional[str], Optional[bool]]:
        """
        Search carrier for the *HEADER* keys and return the tracing key-values.

        :param dc: Dict - The dict potentially containing context
        :return: Tuple[Optional[int], Optional[int], Optional[str], Optional[bool]] - trace_id, span_id, level, synthetic
        """
        trace_id, span_id, level, synthetic = [None] * 4

        # Headers can exist in the standard X-Instana-T/S format or the alternate HTTP_X_INSTANA_T/S style
        try:
            trace_id = (
                dc.get(self.LC_HEADER_KEY_T)
                or dc.get(self.ALT_LC_HEADER_KEY_T)
                or dc.get(self.B_HEADER_KEY_T)
                or dc.get(self.B_ALT_LC_HEADER_KEY_T)
                or dc.get(self.KAFKA_HEADER_KEY_T.lower())
            )
            if trace_id:
                trace_id = header_to_long_id(trace_id)

            span_id = (
                dc.get(self.LC_HEADER_KEY_S)
                or dc.get(self.ALT_LC_HEADER_KEY_S)
                or dc.get(self.B_HEADER_KEY_S)
                or dc.get(self.B_ALT_LC_HEADER_KEY_S)
                or dc.get(self.KAFKA_HEADER_KEY_S.lower())
            )
            if span_id:
                span_id = header_to_id(span_id)

            level = (
                dc.get(self.LC_HEADER_KEY_L)
                or dc.get(self.ALT_LC_HEADER_KEY_L)
                or dc.get(self.B_HEADER_KEY_L)
                or dc.get(self.B_ALT_LC_HEADER_KEY_L)
                or dc.get(self.KAFKA_HEADER_KEY_L_S.lower())
            )
            if level and isinstance(level, bytes):
                level = level.decode("utf-8")

            synthetic = (
                dc.get(self.LC_HEADER_KEY_SYNTHETIC)
                or dc.get(self.ALT_LC_HEADER_KEY_SYNTHETIC)
                or dc.get(self.B_HEADER_KEY_SYNTHETIC)
                or dc.get(self.B_ALT_LC_HEADER_KEY_SYNTHETIC)
            )
            if synthetic:
                synthetic = synthetic in ["1", b"1"]

        except Exception:
            logger.debug("extract error:", exc_info=True)

        return trace_id, span_id, level, synthetic

    def __extract_w3c_trace_context_headers(self, dc):
        """
        Search carrier for the *HEADER* keys and return the tracing key-values

        :param dc: The dict or list potentially containing context
        :return: traceparent, tracestate
        """
        traceparent, tracestate = [None] * 2

        try:
            traceparent = (
                dc.get(self.HEADER_KEY_TRACEPARENT)
                or dc.get(self.ALT_HEADER_KEY_TRACEPARENT)
                or dc.get(self.B_HEADER_KEY_TRACEPARENT)
                or dc.get(self.B_ALT_HEADER_KEY_TRACEPARENT)
            )
            if traceparent and isinstance(traceparent, bytes):
                traceparent = traceparent.decode("utf-8")

            tracestate = (
                dc.get(self.HEADER_KEY_TRACESTATE)
                or dc.get(self.ALT_HEADER_KEY_TRACESTATE)
                or dc.get(self.B_HEADER_KEY_TRACESTATE)
                or dc.get(self.B_ALT_HEADER_KEY_TRACESTATE)
            )
            if tracestate and isinstance(tracestate, bytes):
                tracestate = tracestate.decode("utf-8")

        except Exception:
            logger.debug("extract error:", exc_info=True)

        return traceparent, tracestate

    def extract(
        self, carrier: CarrierT, disable_w3c_trace_context: bool = False
    ) -> Optional[SpanContext]:
        """
        This method overrides one of the Base classes as with the introduction
        of W3C trace context for the HTTP requests more extracting steps and
        logic was required.

        :param disable_w3c_trace_context:
        :param carrier:
        :return: the context or None
        """
        try:
            traceparent, tracestate = [None] * 2
            headers = self.extract_headers_dict(carrier=carrier)
            if headers is None:
                return None
            headers = {k.lower(): v for k, v in headers.items()}

            trace_id, span_id, level, synthetic = self.extract_instana_headers(
                dc=headers
            )
            if not disable_w3c_trace_context:
                traceparent, tracestate = self.__extract_w3c_trace_context_headers(
                    dc=headers
                )

            if traceparent:
                traceparent = self._tp.validate(traceparent)

            if trace_id is None:
                trace_id = INVALID_TRACE_ID
            if span_id is None:
                span_id = INVALID_SPAN_ID

            span_context = self.__determine_span_context(
                trace_id,
                span_id,
                level,
                synthetic,
                traceparent,
                tracestate,
                disable_w3c_trace_context,
            )
            return span_context

        except Exception:
            logger.debug("base_propagator extract error:", exc_info=True)
