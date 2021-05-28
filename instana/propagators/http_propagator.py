# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import re
import sys

from .base_propagator import BasePropagator
from ..log import logger
from ..span_context import SpanContext
from ..util.ids import header_to_id

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

_TRACEPARENT_HEADER_NAME = "traceparent"
_TRACESTATE_HEADER_NAME = "tracestate"
_TRACEPARENT_HEADER_FORMAT = (
        "^[ \t]*([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})"
        + "(-.*)?[ \t]*$"
)
_TRACEPARENT_HEADER_FORMAT_RE = re.compile(_TRACEPARENT_HEADER_FORMAT)


class HTTPPropagator(BasePropagator):
    """
    Instana Propagator for Format.HTTP_HEADERS.

    The HTTP_HEADERS format deals with key-values with string to string mapping.
    The character set should be restricted to HTTP compatible.
    """

    def extract(self, carrier):
        """
        Search carrier for the *HEADER* keys and return a SpanContext or None

        Note: Extract is on the base class since it never really varies in task regardless
        of the propagator in uses.

        :param carrier: The dict or list potentially containing context
        :return: SpanContext or None
        """
        trace_id = None
        span_id = None
        level = 1
        synthetic = False
        dc = None

        try:
            # Attempt to convert incoming <carrier> into a dict
            try:
                if isinstance(carrier, dict):
                    dc = carrier
                elif hasattr(carrier, "__dict__"):
                    dc = carrier.__dict__
                else:
                    dc = dict(carrier)
            except Exception:
                logger.debug("extract: Couln't convert %s", carrier)

            if dc is None:
                return None

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

            ctx = None
            if trace_id is not None and span_id is not None:
                ctx = SpanContext(span_id=span_id,
                                  trace_id=trace_id,
                                  level=level,
                                  baggage={},
                                  sampled=True,
                                  synthetic=synthetic)
            elif synthetic:
                ctx = SpanContext(synthetic=synthetic)

            return ctx

        except Exception:
            logger.debug("extract error:", exc_info=True)

    def inject(self, span_context, carrier):
        try:
            trace_id = span_context.trace_id
            span_id = span_context.span_id

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                carrier[self.HEADER_KEY_T] = trace_id
                carrier[self.HEADER_KEY_S] = span_id
                carrier[self.HEADER_KEY_L] = "1"
            elif isinstance(carrier, list):
                carrier.append((self.HEADER_KEY_T, trace_id))
                carrier.append((self.HEADER_KEY_S, span_id))
                carrier.append((self.HEADER_KEY_L, "1"))
            elif hasattr(carrier, '__setitem__'):
                carrier.__setitem__(self.HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.HEADER_KEY_S, span_id)
                carrier.__setitem__(self.HEADER_KEY_L, "1")
            else:
                raise Exception("Unsupported carrier type", type(carrier))

        except Exception:
            logger.debug("inject error:", exc_info=True)
