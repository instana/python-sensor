# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from ..log import logger
import re


class Traceparent:
    SPECIFICATION_VERSION = "00"
    TRACEPARENT_REGEX = re.compile("^[0-9a-f]{2}-(?!0{32})([0-9a-f]{32})-(?!0{16})([0-9a-f]{16})-[0-9a-f]{2}")

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
            logger.debug("traceparent does not follow version {} specification".format(self.SPECIFICATION_VERSION))
        return None

    @staticmethod
    def get_traceparent_fields(traceparent):
        """
        Parses the validated traceparent header into its fields and returns the fields
        :param traceparent: the original validated traceparent header
        :return: version, trace_id, parent_id, trace_flags
        """
        try:
            traceparent_properties = traceparent.split("-")
            version = traceparent_properties[0]
            trace_id = traceparent_properties[1]
            parent_id = traceparent_properties[2]
            trace_flags = traceparent_properties[3]
            return version, trace_id, parent_id, trace_flags
        except Exception:  # This method is intended to be called with a version 00 validated traceparent
            # This exception handling is added just for making sure we do not throw any unhandled exception
            # if somebody calls the method in the future without a validated traceparent
            return None, None, None, None

    def update_traceparent(self, traceparent, in_trace_id, in_span_id, level):
        """
        This method updates the traceparent header or generates one if there was no traceparent incoming header or it
        was invalid
        :param traceparent: the original validated traceparent header
        :param in_trace_id: instana trace id, used when there is no preexisting trace_id from the traceparent header
        :param in_span_id: instana span id, used to update the parent id of the traceparent header
        :param level: instana level, used to determine the value of sampled flag of the traceparent header
        :return: the updated traceparent header
        """
        mask = 1 << 0
        trace_flags = 0
        if traceparent is None:  # modify the trace_id part only when it was not present at all
            trace_id = in_trace_id.zfill(32)
            version = self.SPECIFICATION_VERSION
        else:
            version, trace_id, _, trace_flags = self.get_traceparent_fields(traceparent)
            trace_flags = int(trace_flags, 16)

        parent_id = in_span_id.zfill(16)
        trace_flags = (trace_flags & ~mask) | ((level << 0) & mask)
        trace_flags = format(trace_flags, '0>2x')

        traceparent = "{version}-{traceid}-{parentid}-{trace_flags}".format(version=version,
                                                                        traceid=trace_id,
                                                                        parentid=parent_id,
                                                                        trace_flags=trace_flags)
        return traceparent
