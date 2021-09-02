# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys

from instana.log import logger
from instana.util.ids import header_to_id, header_to_long_id
from instana.span_context import SpanContext
from instana.w3c_trace_context.traceparent import Traceparent
from instana.w3c_trace_context.tracestate import Tracestate
import os

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3


# The carrier can be a dict or a list.
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


class BasePropagator(object):
    HEADER_KEY_T = 'X-INSTANA-T'
    HEADER_KEY_S = 'X-INSTANA-S'
    HEADER_KEY_L = 'X-INSTANA-L'
    HEADER_KEY_SYNTHETIC = 'X-INSTANA-SYNTHETIC'
    HEADER_KEY_TRACEPARENT = "traceparent"
    HEADER_KEY_TRACESTATE = "tracestate"

    LC_HEADER_KEY_T = 'x-instana-t'
    LC_HEADER_KEY_S = 'x-instana-s'
    LC_HEADER_KEY_L = 'x-instana-l'
    LC_HEADER_KEY_SYNTHETIC = 'x-instana-synthetic'

    ALT_LC_HEADER_KEY_T = 'http_x_instana_t'
    ALT_LC_HEADER_KEY_S = 'http_x_instana_s'
    ALT_LC_HEADER_KEY_L = 'http_x_instana_l'
    ALT_LC_HEADER_KEY_SYNTHETIC = 'http_x_instana_synthetic'
    ALT_HEADER_KEY_TRACEPARENT = "http_traceparent"
    ALT_HEADER_KEY_TRACESTATE = "http_tracestate"

    # ByteArray variations
    B_HEADER_KEY_T = b'x-instana-t'
    B_HEADER_KEY_S = b'x-instana-s'
    B_HEADER_KEY_L = b'x-instana-l'
    B_HEADER_KEY_SYNTHETIC = b'x-instana-synthetic'
    B_HEADER_SERVER_TIMING = b'server-timing'
    B_HEADER_KEY_TRACEPARENT = b'traceparent'
    B_HEADER_KEY_TRACESTATE = b'tracestate'

    B_ALT_LC_HEADER_KEY_T = b'http_x_instana_t'
    B_ALT_LC_HEADER_KEY_S = b'http_x_instana_s'
    B_ALT_LC_HEADER_KEY_L = b'http_x_instana_l'
    B_ALT_LC_HEADER_KEY_SYNTHETIC = b'http_x_instana_synthetic'
    B_ALT_HEADER_KEY_TRACEPARENT = b'http_traceparent'
    B_ALT_HEADER_KEY_TRACESTATE = b'http_tracestate'

    def __init__(self):
        self._tp = Traceparent()
        self._ts = Tracestate()

    @staticmethod
    def _extract_headers_dict(carrier):
        """
        This method converts the incoming carrier into a dict
        :param carrier:
        :return: dc dictionary
        """
        try:
            if isinstance(carrier, dict):
                dc = carrier
            elif hasattr(carrier, "__dict__"):
                dc = carrier.__dict__
            else:
                dc = dict(carrier)
        except Exception:
            logger.debug("extract: Couldn't convert %s", carrier)
            dc = None

        return dc

    @staticmethod
    def _get_ctx_level(level):
        """
        Extract the level value and return it, as it may include correlation values
        :param level:
        :return:
        """
        try:
            ctx_level = int(level.split(",")[0]) if level else 1
        except Exception:
            ctx_level = 1
        return ctx_level

    @staticmethod
    def _set_correlation_properties(level, ctx):
        """
        Set the correlation values if they are present
        :param level:
        :param ctx:
        :return:
        """
        try:
            ctx.correlation_type = level.split(",")[1].split("correlationType=")[1].split(";")[0]
            if "correlationId" in level:
                ctx.correlation_id = level.split(",")[1].split("correlationId=")[1].split(";")[0]
        except Exception:
            logger.debug("extract instana correlation type/id error:", exc_info=True)

    def _get_participating_trace_context(self, span_context):
        """
        This method is called for getting the updated traceparent and tracestate values
        :param span_context:
        :return: traceparent, tracestate
        """
        if span_context.long_trace_id and not span_context.trace_parent:
            tp_trace_id = span_context.long_trace_id
        else:
            tp_trace_id = span_context.trace_id
        traceparent = span_context.traceparent
        tracestate = span_context.tracestate
        traceparent = self._tp.update_traceparent(traceparent, tp_trace_id, span_context.span_id, span_context.level)
        tracestate = self._ts.update_tracestate(tracestate, span_context.trace_id, span_context.span_id)
        return traceparent, tracestate

    def __determine_span_context(self, trace_id, span_id, level, synthetic, traceparent, tracestate,
                                 disable_w3c_trace_context):
        """
        This method determines the span context depending on a set of conditions being met
        Detailed description of the conditions can be found here:
        https://github.com/instana/technical-documentation/tree/master/tracing/specification#http-processing-for-instana-tracers
        :param trace_id: instana trace id
        :param span_id: instana span id
        :param level: instana level
        :param synthetic: instana synthetic
        :param traceparent:
        :param tracestate:
        :param disable_w3c_trace_context: flag used to enable w3c trace context only on HTTP requests
        :return: ctx
        """
        correlation = False
        disable_traceparent = os.environ.get("INSTANA_DISABLE_W3C_TRACE_CORRELATION", "")
        instana_ancestor = None
        ctx = SpanContext()
        if level and "correlationType" in level:
            trace_id, span_id = [None] * 2
            correlation = True

        ctx_level = self._get_ctx_level(level)

        if trace_id and span_id:
            ctx.trace_id = trace_id[-16:]  # only the last 16 chars
            ctx.span_id = span_id[-16:]  # only the last 16 chars
            ctx.level = ctx_level
            ctx.synthetic = synthetic is not None

            if len(trace_id) > 16:
                ctx.long_trace_id = trace_id

        elif not disable_w3c_trace_context and traceparent and trace_id is None and span_id is None:
            _, tp_trace_id, tp_parent_id, _ = self._tp.get_traceparent_fields(traceparent)

            if tracestate and "in=" in tracestate:
                instana_ancestor = self._ts.get_instana_ancestor(tracestate)

            if disable_traceparent == "":
                ctx.trace_id = tp_trace_id[-16:]
                ctx.span_id = tp_parent_id
                ctx.level = ctx_level
                ctx.synthetic = synthetic is not None
                ctx.trace_parent = True
                ctx.instana_ancestor = instana_ancestor
                ctx.long_trace_id = tp_trace_id
            else:
                if instana_ancestor:
                    ctx.trace_id = instana_ancestor.t
                    ctx.span_id = instana_ancestor.p
                    ctx.level = ctx_level
                    ctx.synthetic = synthetic is not None

        elif synthetic:
            ctx.synthetic = synthetic

        if correlation:
            self._set_correlation_properties(level, ctx)

        if traceparent:
            ctx.traceparent = traceparent
            ctx.tracestate = tracestate

        return ctx

    def __extract_instana_headers(self, dc):
        """
        Search carrier for the *HEADER* keys and return the tracing key-values

        :param dc: The dict or list potentially containing context
        :return: trace_id, span_id, level, synthetic
        """
        trace_id, span_id, level, synthetic = [None] * 4

        # Headers can exist in the standard X-Instana-T/S format or the alternate HTTP_X_INSTANA_T/S style
        try:
            trace_id = dc.get(self.LC_HEADER_KEY_T) or dc.get(self.ALT_LC_HEADER_KEY_T) or dc.get(
                self.B_HEADER_KEY_T) or dc.get(self.B_ALT_LC_HEADER_KEY_T)
            if trace_id:
                trace_id = header_to_long_id(trace_id)

            span_id = dc.get(self.LC_HEADER_KEY_S) or dc.get(self.ALT_LC_HEADER_KEY_S) or dc.get(
                self.B_HEADER_KEY_S) or dc.get(self.B_ALT_LC_HEADER_KEY_S)
            if span_id:
                span_id = header_to_id(span_id)

            level = dc.get(self.LC_HEADER_KEY_L) or dc.get(self.ALT_LC_HEADER_KEY_L) or dc.get(
                self.B_HEADER_KEY_L) or dc.get(self.B_ALT_LC_HEADER_KEY_L)
            if level and PY3 is True and isinstance(level, bytes):
                level = level.decode("utf-8")

            synthetic = dc.get(self.LC_HEADER_KEY_SYNTHETIC) or dc.get(self.ALT_LC_HEADER_KEY_SYNTHETIC) or dc.get(
                self.B_HEADER_KEY_SYNTHETIC) or dc.get(self.B_ALT_LC_HEADER_KEY_SYNTHETIC)
            if synthetic:
                synthetic = synthetic in ['1', b'1']

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
            traceparent = dc.get(self.HEADER_KEY_TRACEPARENT) or dc.get(self.ALT_HEADER_KEY_TRACEPARENT) or dc.get(
                self.B_HEADER_KEY_TRACEPARENT) or dc.get(self.B_ALT_HEADER_KEY_TRACEPARENT)
            if traceparent and PY3 is True and isinstance(traceparent, bytes):
                traceparent = traceparent.decode("utf-8")

            tracestate = dc.get(self.HEADER_KEY_TRACESTATE) or dc.get(self.ALT_HEADER_KEY_TRACESTATE) or dc.get(
                self.B_HEADER_KEY_TRACESTATE) or dc.get(self.B_ALT_HEADER_KEY_TRACESTATE)
            if tracestate and PY3 is True and isinstance(tracestate, bytes):
                tracestate = tracestate.decode("utf-8")

        except Exception:
            logger.debug("extract error:", exc_info=True)

        return traceparent, tracestate

    def extract(self, carrier, disable_w3c_trace_context=False):
        """
        This method overrides the one of the Baseclass as with the introduction of W3C trace context for the HTTP
        requests more extracting steps and logic was required
        :param disable_w3c_trace_context:
        :param carrier:
        :return: the context or None
        """
        try:
            traceparent, tracestate = [None] * 2
            headers = self._extract_headers_dict(carrier=carrier)
            if headers is None:
                return None
            headers = {k.lower(): v for k, v in headers.items()}

            trace_id, span_id, level, synthetic = self.__extract_instana_headers(dc=headers)
            if not disable_w3c_trace_context:
                traceparent, tracestate = self.__extract_w3c_trace_context_headers(dc=headers)

            if traceparent:
                traceparent = self._tp.validate(traceparent)

            ctx = self.__determine_span_context(trace_id, span_id, level, synthetic, traceparent, tracestate,
                                                disable_w3c_trace_context)

            return ctx
        except Exception:
            logger.debug("extract error:", exc_info=True)