# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys
from ..log import logger
from .base_propagator import BasePropagator
from ..util.ids import header_to_id
from ..span_context import SpanContext

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3


class HTTPPropagator(BasePropagator):
    """
    Instana Propagator for Format.HTTP_HEADERS.

    The HTTP_HEADERS format deals with key-values with string to string mapping.
    The character set should be restricted to HTTP compatible.
    """

    def __init__(self):
        super(HTTPPropagator, self).__init__()

    def inject(self, span_context, carrier):
        try:
            trace_id = span_context.trace_id
            span_id = span_context.span_id
            level = span_context.level

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                carrier[self.HEADER_KEY_T] = trace_id
                carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = str(level)
            elif isinstance(carrier, list):
                carrier.append((self.HEADER_KEY_T, trace_id))
                carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, str(level)))
            elif hasattr(carrier, '__setitem__'):
                carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, str(level))
            else:
                raise Exception("Unsupported carrier type", type(carrier))

        except Exception:
            logger.debug("inject error:", exc_info=True)

    def extract(self, carrier):
        """
        This method overrides the one of the Baseclass as with the introduction of W3C trace context for the HTTP
        requests more extracting steps and logic was required
        :param carrier:
        :return: the context or None
        """
        try:
            headers = self._extract_headers_dict(carrier=carrier)
            if headers is None:
                return None
            headers = {k.lower(): v for k, v in headers.items()}

            trace_id, span_id, level, synthetic = self.__extract_instana_headers(dc=headers)

            ctx = self.__determine_span_context(trace_id, span_id, level, synthetic)

            return ctx
        except Exception:
            logger.debug("extract error:", exc_info=True)

    def __extract_instana_headers(self, dc):
        """
        Search carrier for the *HEADER* keys and return the tracing key-values

        :param dc: The dict or list potentially containing context
        :return: trace_id, span_id, level, synthetic, traceparent, tracestate
        """
        trace_id, span_id, level, synthetic, traceparent, tracestate = [None] * 6

        # Headers can exist in the standard X-Instana-T/S format or the alternate HTTP_X_INSTANA_T/S style
        try:
            trace_id = dc.get(self.LC_HEADER_KEY_T) or dc.get(self.ALT_LC_HEADER_KEY_T) or dc.get(
                self.LC_HEADER_KEY_T.encode("utf-8")) or dc.get(self.ALT_LC_HEADER_KEY_T.encode("utf-8"))
            if trace_id:
                trace_id = header_to_id(trace_id)

            span_id = dc.get(self.LC_HEADER_KEY_S) or dc.get(self.ALT_LC_HEADER_KEY_S) or dc.get(
                self.LC_HEADER_KEY_S.encode("utf-8")) or dc.get(self.ALT_LC_HEADER_KEY_S.encode("utf-8"))
            if span_id:
                span_id = header_to_id(span_id)

            level = dc.get(self.LC_HEADER_KEY_L) or dc.get(self.ALT_LC_HEADER_KEY_L) or dc.get(
                self.LC_HEADER_KEY_L.encode("utf-8")) or dc.get(self.ALT_LC_HEADER_KEY_L.encode("utf-8"))
            if level and PY3 is True and isinstance(level, bytes):
                level = level.decode("utf-8")

            synthetic = dc.get(self.LC_HEADER_KEY_SYNTHETIC) or dc.get(self.ALT_LC_HEADER_KEY_SYNTHETIC) or dc.get(
                self.LC_HEADER_KEY_SYNTHETIC.encode("utf-8")) or dc.get(
                self.ALT_LC_HEADER_KEY_SYNTHETIC.encode("utf-8"))
            if synthetic:
                synthetic = synthetic in ['1', b'1']

        except Exception:
            logger.debug("extract error:", exc_info=True)

        return trace_id, span_id, level, synthetic

    def __determine_span_context(self, trace_id, span_id, level, synthetic):
        """
        This method determines the span context
        :param **kwargs:
        :param **kwargs:
        :param trace_id: instana trace id
        :param span_id: instana span id
        :param level: instana level
        :param synthetic: instana synthetic
        :return: ctx
        """
        correlation = False
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

        elif synthetic:
            ctx.synthetic = synthetic

        if correlation:
            self._set_correlation_properties(level, ctx)

        return ctx
