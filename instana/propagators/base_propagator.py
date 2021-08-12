# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys

from ..log import logger

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

    LC_HEADER_KEY_T = 'x-instana-t'
    LC_HEADER_KEY_S = 'x-instana-s'
    LC_HEADER_KEY_L = 'x-instana-l'
    LC_HEADER_KEY_SYNTHETIC = 'x-instana-synthetic'

    ALT_LC_HEADER_KEY_T = 'http_x_instana_t'
    ALT_LC_HEADER_KEY_S = 'http_x_instana_s'
    ALT_LC_HEADER_KEY_L = 'http_x_instana_l'
    ALT_LC_HEADER_KEY_SYNTHETIC = 'http_x_instana_synthetic'

    HEADER_KEY_TRACEPARENT = "traceparent"
    HEADER_KEY_TRACESTATE = "tracestate"

    ALT_HEADER_KEY_TRACEPARENT = "http_traceparent"
    ALT_HEADER_KEY_TRACESTATE = "http_tracestate"

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
