# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys

from ..log import logger
from .base_propagator import BasePropagator
from ..w3c_trace_context.treceparent import Traceparent
from ..w3c_trace_context.tracestate import Tracestate, InstanaAncestor

from ..util.ids import header_to_id
from ..span_context import SpanContext
import os

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3


class HTTPPropagator(BasePropagator):
    """
    Instana Propagator for Format.HTTP_HEADERS.

    The HTTP_HEADERS format deals with key-values with string to string mapping.
    The character set should be restricted to HTTP compatible.
    """
    HEADER_KEY_TRACEPARENT = "traceparent"
    HEADER_KEY_TRACESTATE = "tracestate"

    def __init__(self):
        self.__traceparent = Traceparent()
        self.__tracestate = Tracestate()
        super(HTTPPropagator, self).__init__()

    def inject(self, span_context, carrier):
        try:
            trace_id = span_context.trace_id
            span_id = span_context.span_id
            level = span_context.level
            self.__traceparent.update_traceparent(trace_id, span_id, level)
            self.__tracestate.update_tracestate(trace_id, span_id)
            traceparent = self.__traceparent.traceparent
            tracestate = self.__tracestate.tracestate

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                if traceparent and tracestate:
                    carrier[self.HEADER_KEY_TRACEPARENT] = traceparent
                    carrier[self.HEADER_KEY_TRACESTATE] = tracestate
                carrier[self.HEADER_KEY_T] = trace_id
                carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = "1"
            elif isinstance(carrier, list):
                if traceparent and tracestate:
                    carrier.append((self.HEADER_KEY_TRACEPARENT, traceparent))
                    carrier.append((self.HEADER_KEY_TRACESTATE, tracestate))
                carrier.append((self.HEADER_KEY_T, trace_id))
                carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, "1"))
            elif hasattr(carrier, '__setitem__'):
                if traceparent and tracestate:
                    carrier.__setitem__(self.HEADER_KEY_TRACEPARENT, traceparent)
                    carrier.__setitem__(self.HEADER_KEY_TRACESTATE, tracestate)
                carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, "1")
            else:
                raise Exception("Unsupported carrier type", type(carrier))

        except Exception:
            logger.debug("inject error:", exc_info=True)

    def __extract_headers_dict(self, carrier):
        # Attempt to convert incoming <carrier> into a dict
        # TODO: Support for multiple header fields with the same name? (e.g. tracestate)
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
        try:
            headers = self.__extract_headers_dict(carrier=carrier)
            if headers is None:
                return None
            headers = {k.lower(): v for k, v in headers.items()}
            self.__traceparent.extract_traceparent(headers)
            self.__tracestate.extract_tracestate(headers)

            # TODO use traceparent and tracestate
            trace_id, span_id, level, synthetic = self.__extract_instana_headers(dc=headers)
            ctx = self.__determine_span_context(trace_id, span_id, level, synthetic)

            return ctx
        except Exception:
            logger.debug("extract error:", exc_info=True)

    def __determine_span_context(self, trace_id, span_id, level, synthetic):
        disable_traceparent = os.environ.get("INSTANA_W3C_DISABLE_TRACE_CORRELATION", "")

        ctx = None
        if self.__traceparent.traceparent and all(v is None for v in [trace_id, span_id, level]):
            if disable_traceparent == "":
                ctx = SpanContext(span_id=self.__traceparent.parent_id,
                                  trace_id=self.__traceparent.trace_id[-16:],
                                  level=1,
                                  baggage={},
                                  sampled=True,
                                  synthetic=False if synthetic is None else True)

                ctx.trace_parent = True

                try:
                    if self.__tracestate.tracestate and "in=" in self.__tracestate.tracestate:
                        in_list_member = self.__tracestate.tracestate.split("in=")[1].split(",")[0]
                        ctx.instana_ancestor = InstanaAncestor(trace_id=in_list_member.split(";")[0],
                                                               parent_id=in_list_member.split(";")[1])

                except Exception as e:
                    logger.debug("extract instana ancestor error:", exc_info=True)

                ctx.long_trace_id = self.__traceparent.trace_id
            else:
                try:
                    if self.__tracestate.tracestate and "in=" in self.__tracestate.tracestate:
                        in_list_member = self.__tracestate.tracestate.split("in=")[1].split(",")[0]
                        ctx.instana_ancestor = InstanaAncestor(trace_id=in_list_member.split(";")[0],
                                                               parent_id=in_list_member.split(";")[1])

                        ctx = SpanContext(span_id=in_list_member.split(";")[1],
                                          trace_id=in_list_member.split(";")[0],
                                          level=1,
                                          baggage={},
                                          sampled=True,
                                          synthetic=False if synthetic is None else True)
                except Exception as e:
                    logger.debug("extract instana ancestor error:", exc_info=True)

        elif trace_id and span_id:
            try:
                if "correlationType" in level:
                    ctx.correlation_type = level.split(",")[1].split("correlationType=")[1].split(";")[0]
                if "correlationId" in level:
                    ctx.correlation_id = level.split(",")[1].split("correlationId=")[1].split(";")[0]
            except Exception as e:
                logger.debug("extract instana correlation type/id error:", exc_info=True)

            ctx = SpanContext(span_id=span_id,
                              trace_id=trace_id,
                              level=int(level.split(",")[0]),
                              baggage={},
                              sampled=True,
                              synthetic=False if synthetic is None else True)
        elif synthetic:
            ctx = SpanContext(synthetic=synthetic)
        return ctx

    def __extract_instana_headers(self, dc):
        """
        Search carrier for the *HEADER* keys and return a SpanContext or None

        Note: Extract is on the base class since it never really varies in task regardless
        of the propagator in uses.

        :param dc: The dict or list potentially containing context
        :return: SpanContext or None
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
                    level = dc[key]
                elif self.LC_HEADER_KEY_SYNTHETIC == lc_key:
                    synthetic = dc[key] in ['1', b'1']

                elif self.ALT_LC_HEADER_KEY_T == lc_key:
                    trace_id = header_to_id(dc[key])
                elif self.ALT_LC_HEADER_KEY_S == lc_key:
                    span_id = header_to_id(dc[key])
                elif self.ALT_LC_HEADER_KEY_L == lc_key:
                    level = dc[key]
                elif self.ALT_LC_HEADER_KEY_SYNTHETIC == lc_key:
                    synthetic = dc[key] in ['1', b'1']

        except Exception:
            logger.debug("extract error:", exc_info=True)

        return trace_id, span_id, level, synthetic
