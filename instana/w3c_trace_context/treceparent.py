# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from ..log import logger
import re


class Traceparent:
    SPECIFICATION_VERSION = "00"
    TRACEPARENT_REGEX = re.compile("[0-9a-f]{2}-(?!0{32})([0-9a-f]{32})-(?!0{16})([0-9a-f]{16})-[0-9a-f]{2}")

    def __validate(self, traceparent):
        """
        Method used to validate the traceparent header
        :param traceparent: string
        :return: True or False
        """
        try:
            if self.TRACEPARENT_REGEX.match(traceparent) and traceparent.split("-")[0] == self.SPECIFICATION_VERSION:
                return True
        except Exception:
            logger.debug("traceparent does not follow version 00 specification")
        return False

    def extract_traceparent(self, headers):
        """
        Extracts from the headers dict the traceparent key/value and validates its value
        :param headers: dict with headers
        :return: the validated traceparent or None
        """
        traceparent = headers.get('traceparent', None)
        if traceparent and self.__validate(traceparent):
            return traceparent
        else:
            return None

    @staticmethod
    def get_traceparent_fields(traceparent):
        """
        Parses the validated traceparent header into its fields and returns the fields
        :param traceparent: the original validated traceparent header
        :return: trace_id, parent_id, sampled
        """
        traceparent_properties = traceparent.split("-")
        trace_id = traceparent_properties[1]
        parent_id = traceparent_properties[2]
        sampled = traceparent_properties[3]
        return trace_id, parent_id, sampled

    def update_traceparent(self, traceparent, in_trace_id, in_span_id, level):
        """
        This method updates the traceparent header or generates one if there was no traceparent incoming header or it
        was invalid
        :param traceparent: the original validated traceparent header
        :param in_trace_id: instana trace id, used when there is no preexisting trace_id from the traceparent header
        :param in_span_id: instana span id, used to update the parent id of the traceparent header
        :param level: instana level, used to determine the value of sampled flag of the traceparent header
        :return: sets the updated traceparent header
        """

        if traceparent is None:  # modify the trace_id part only when it was not present at all
            trace_id = in_trace_id.zfill(32)
        else:
            trace_id, _, _ = self.get_traceparent_fields(traceparent)
        parent_id = in_span_id.zfill(16)
        sampled = "01" if level == 1 else "00"
        traceparent = "{version}-{traceid}-{parentid}-{sampled}".format(version=self.SPECIFICATION_VERSION,
                                                                        traceid=trace_id,
                                                                        parentid=parent_id,
                                                                        sampled=sampled)
        return traceparent
