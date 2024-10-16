# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import re
from typing import Optional, Tuple

from opentelemetry.trace.span import (
    format_span_id,
    format_trace_id,
)

from instana.log import logger
from instana.util.ids import header_to_id, header_to_long_id

# See https://www.w3.org/TR/trace-context-2/#trace-flags for details on the bitmasks.
SAMPLED_BITMASK = 0b1;

class Traceparent:
    SPECIFICATION_VERSION = "00"
    TRACEPARENT_REGEX = re.compile(
        "^[0-9a-f][0-9a-e]-(?!0{32})([0-9a-f]{32})-(?!0{16})([0-9a-f]{16})-[0-9a-f]{2}"
    )

    def validate(self, traceparent):
        """
        Method used to validate the traceparent header
        :param traceparent: string
        :return: traceparent or None
        """
        try:
            if self.TRACEPARENT_REGEX.match(traceparent):
                return traceparent
        except Exception:
            logger.debug(
                "traceparent does not follow version {} specification".format(
                    self.SPECIFICATION_VERSION
                )
            )
        return None

    @staticmethod
    def get_traceparent_fields(traceparent: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[bool]]:
        """
        Parses the validated traceparent header into its fields and returns the fields
        :param traceparent: the original validated traceparent header
        :return: version, trace_id, parent_id, sampled_flag
        """
        try:
            traceparent_properties = traceparent.split("-")
            version = traceparent_properties[0]
            trace_id = header_to_long_id(traceparent_properties[1])
            parent_id = header_to_id(traceparent_properties[2])
            flags = int(traceparent_properties[3], 16)
            sampled_flag = (flags & SAMPLED_BITMASK) == SAMPLED_BITMASK
            return version, trace_id, parent_id, sampled_flag
        except Exception as err:  # This method is intended to be called with a version 00 validated traceparent
            # This exception handling is added just for making sure we do not throw any unhandled exception
            # if somebody calls the method in the future without a validated traceparent
            logger.debug("Parsing the traceparent failed: {}".format(err))
            return None, None, None, None

    def update_traceparent(
        self,
        traceparent: Optional[str],
        in_trace_id: int,
        in_span_id: int,
        level: int,
    ) -> str:
        """
        This method updates the traceparent header or generates one if there was no traceparent incoming header or it
        was invalid
        :param traceparent: the original validated traceparent header
        :param in_trace_id: instana trace id, used when there is no preexisting trace_id from the traceparent header
        :param in_span_id: instana span id, used to update the parent id of the traceparent header
        :param level: instana level, used to determine the value of sampled flag of the traceparent header
        :return: the updated traceparent header
        """
        if (
            traceparent is None
        ):  # modify the trace_id part only when it was not present at all
            trace_id = (
                in_trace_id.zfill(32)
                if not isinstance(in_trace_id, int)
                else in_trace_id
            )
        else:
            # - We do not need the incoming upstream parent span ID for the header we sent downstream.
            # - We also do not care about the incoming version: The version field we sent downstream needs to match the
            #   format of the traceparent header we produce here, so we always send the version _we_ support downstream,
            #   even if the header coming from upstream supported a different version.
            # - Finally, we also do not care about the incoming sampled flag , we only need to communicate our own
            #   sampling decision downstream. The sampling decisions from our upstream is irrelevant for what we send
            #   downstream.
            _, trace_id, _, _ = self.get_traceparent_fields(traceparent)

        parent_id = (
            in_span_id.zfill(16) if not isinstance(in_span_id, int) else in_span_id
        )
        flags = level & SAMPLED_BITMASK
        flags = format(flags, "0>2x")

        if isinstance(trace_id, str):
            trace_id_out = trace_id
        else:
            trace_id_out = format_trace_id(trace_id)

        traceparent = f"{self.SPECIFICATION_VERSION}-{trace_id_out}-{format_span_id(parent_id)}-{flags}"
        return traceparent
