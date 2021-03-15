# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys

from ..log import logger
from ..util.ids import header_to_id
from ..span_context import SpanContext

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


class BasePropagator():
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
