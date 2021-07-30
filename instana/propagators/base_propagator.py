# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys

from ..log import logger
from ..util.ids import header_to_id
from ..span_context import SpanContext
from ..w3c_trace_context.treceparent import Traceparent
from ..w3c_trace_context.tracestate import Tracestate
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
    UC_HEADER_KEY_T = 'X-INSTANA-T'
    UC_HEADER_KEY_S = 'X-INSTANA-S'
    UC_HEADER_KEY_L = 'X-INSTANA-L'
    UC_HEADER_KEY_SYNTHETIC = 'X-INSTANA-SYNTHETIC'

    HEADER_KEY_T = 'X-INSTANA-T'
    HEADER_KEY_S = 'X-INSTANA-S'
    HEADER_KEY_L = 'X-INSTANA-L'
    HEADER_KEY_SYNTHETIC = 'X-INSTANA-SYNTHETIC'

    LC_HEADER_KEY_T = 'x-instana-t'
    LC_HEADER_KEY_S = 'x-instana-s'
    LC_HEADER_KEY_L = 'x-instana-l'
    LC_HEADER_KEY_SYNTHETIC = 'x-instana-synthetic'

    ALT_HEADER_KEY_T = 'HTTP_X_INSTANA_T'
    ALT_HEADER_KEY_S = 'HTTP_X_INSTANA_S'
    ALT_HEADER_KEY_L = 'HTTP_X_INSTANA_L'
    ALT_LC_HEADER_KEY_T = 'http_x_instana_t'
    ALT_LC_HEADER_KEY_S = 'http_x_instana_s'
    ALT_LC_HEADER_KEY_L = 'http_x_instana_l'
    ALT_LC_HEADER_KEY_SYNTHETIC = 'http_x_instana_synthetic'

    HEADER_KEY_TRACEPARENT = "traceparent"
    HEADER_KEY_TRACESTATE = "tracestate"

    def __init__(self):
        self.__tp = Traceparent()
        self.__ts = Tracestate()

    def __extract_headers_dict(self, carrier):
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

    def extract(self, carrier):
        """
        This method overrides the one of the Baseclass as with the introduction of W3C trace context for the HTTP
        requests more extracting steps and logic was required
        :param carrier:
        :return: the context or None
        """
        try:
            headers = self.__extract_headers_dict(carrier=carrier)
            if headers is None:
                return None
            headers = {k.lower(): v for k, v in headers.items()}
            traceparent = self.__tp.extract_traceparent(headers)
            tracestate = self.__ts.extract_tracestate(headers)

            trace_id, span_id, level, synthetic = self.__extract_instana_headers(dc=headers)
            ctx = self.__determine_span_context(trace_id, span_id, level, synthetic, traceparent, tracestate)

            return ctx
        except Exception:
            logger.debug("extract error:", exc_info=True)

    def __determine_span_context(self, trace_id, span_id, level, synthetic, traceparent, tracestate):
        """
        This method determines the span context depending on a set of conditions being met
        Detailed description of the conditions can be found here:
        https://github.com/instana/technical-documentation/tree/master/tracing/specification#http-processing-for-instana-tracers
        :param trace_id: instana trace id
        :param span_id: instana span id
        :param level: instana level
        :param synthetic: instana synthetic
        :return: ctx or None
        """
        disable_traceparent = os.environ.get("INSTANA_W3C_DISABLE_TRACE_CORRELATION", "")

        ctx = None
        if level and "correlationType" in level:
            trace_id = None
            span_id = None

        if traceparent and all(v is None for v in [trace_id, span_id]):
            tp_trace_id, tp_parent_id, tp_sampled = self.__tp.get_traceparent_fields(traceparent)
            if disable_traceparent == "":
                ctx = SpanContext(span_id=tp_parent_id,
                                  trace_id=tp_trace_id[-16:],
                                  level=int(level.split(",")[0]) if level else 1,
                                  baggage={},
                                  sampled=True,
                                  synthetic=False if synthetic is None else True)

                ctx.trace_parent = True

                if tracestate and "in=" in tracestate:
                    instana_ancestor = self.__ts.get_instana_ancestor(tracestate)
                    ctx.instana_ancestor = instana_ancestor

                ctx.long_trace_id = tp_trace_id
            else:
                try:
                    if tracestate and "in=" in tracestate:
                        instana_ancestor = self.__ts.get_instana_ancestor(tracestate)

                        ctx = SpanContext(span_id=instana_ancestor.p,
                                          trace_id=instana_ancestor.t,
                                          level=int(level.split(",")[0]) if level else 1,
                                          baggage={},
                                          sampled=True,
                                          synthetic=False if synthetic is None else True)

                        ctx.instana_ancestor = instana_ancestor
                except Exception as e:
                    logger.debug("extract instana ancestor error:", exc_info=True)

            try:
                if level and "correlationType" in level:
                    ctx.correlation_type = level.split(",")[1].split("correlationType=")[1].split(";")[0]
                if level and "correlationId" in level:
                    ctx.correlation_id = level.split(",")[1].split("correlationId=")[1].split(";")[0]
            except Exception as e:
                logger.debug("extract instana correlation type/id error:", exc_info=True)

        elif trace_id and span_id:

            ctx = SpanContext(span_id=span_id,
                              trace_id=trace_id,
                              level=int(level.split(",")[0]) if level else 1,
                              baggage={},
                              sampled=True,
                              synthetic=False if synthetic is None else True)

        elif synthetic:
            ctx = SpanContext(synthetic=synthetic)

        ctx.traceparent = traceparent
        ctx.tracestate = tracestate

        return ctx

    def __extract_instana_headers(self, dc):
        """
        Search carrier for the *HEADER* keys and return a SpanContext or None

        :param dc: The dict or list potentially containing context
        :return: trace_id, span_id, level, synthetic
        """
        trace_id = None
        span_id = None
        level = None
        synthetic = None

        try:
            # Headers can exist in the standard X-Instana-T/S format or the alternate HTTP_X_INSTANA_T/S style
            # We do a case insensitive search to cover all possible variations of incoming headers.
            for key in dc.keys():
                lc_key = None

                if PY3 is True and isinstance(key, bytes):
                    lc_key = key.decode("utf-8").lower()
                else:
                    lc_key = key.lower()

                if self.LC_HEADER_KEY_T == lc_key:
                    trace_id = header_to_id(dc[key])
                elif self.LC_HEADER_KEY_S == lc_key:
                    span_id = header_to_id(dc[key])
                elif self.LC_HEADER_KEY_L == lc_key:
                    level = dc[key].decode("utf-8") if PY3 is True and isinstance(dc[key], bytes) else dc[key]
                elif self.LC_HEADER_KEY_SYNTHETIC == lc_key:
                    synthetic = dc[key] in ['1', b'1']

                elif self.ALT_LC_HEADER_KEY_T == lc_key:
                    trace_id = header_to_id(dc[key])
                elif self.ALT_LC_HEADER_KEY_S == lc_key:
                    span_id = header_to_id(dc[key])
                elif self.ALT_LC_HEADER_KEY_L == lc_key:
                    level = dc[key].decode("utf-8") if PY3 is True and isinstance(dc[key], bytes) else dc[key]
                elif self.ALT_LC_HEADER_KEY_SYNTHETIC == lc_key:
                    synthetic = dc[key] in ['1', b'1']

        except Exception:
            logger.debug("extract error:", exc_info=True)

        return trace_id, span_id, level, synthetic
