# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

from ..log import logger
from .base_propagator import BasePropagator


class TextPropagator(BasePropagator):
    """
    Instana context propagator for TEXT_MAP.

    The TEXT_MAP deals with key-values with string to string mapping.
    The character set is unrestricted.
    """

    def inject(self, span_context, carrier):
        try:
            trace_id = span_context.trace_id
            span_id = span_context.span_id

            if isinstance(carrier, dict) or hasattr(carrier, "__dict__"):
                carrier[self.LC_HEADER_KEY_T] = trace_id
                carrier[self.LC_HEADER_KEY_S] = span_id
                carrier[self.LC_HEADER_KEY_L] = "1"
            elif isinstance(carrier, list):
                carrier.append((self.LC_HEADER_KEY_T, trace_id))
                carrier.append((self.LC_HEADER_KEY_S, span_id))
                carrier.append((self.LC_HEADER_KEY_L, "1"))
            elif isinstance(carrier, tuple):
                carrier = carrier.__add__(((self.LC_HEADER_KEY_T, trace_id),))
                carrier = carrier.__add__(((self.LC_HEADER_KEY_S, span_id),))
                carrier = carrier.__add__(((self.LC_HEADER_KEY_L, "1"),))
            elif hasattr(carrier, '__setitem__'):
                carrier.__setitem__(self.LC_HEADER_KEY_T, trace_id)
                carrier.__setitem__(self.LC_HEADER_KEY_S, span_id)
                carrier.__setitem__(self.LC_HEADER_KEY_L, "1")
            else:
                raise Exception("Unsupported carrier type", type(carrier))

            return carrier
        except Exception:
            logger.debug("inject error:", exc_info=True)
