# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from ..log import logger
import re


class Traceparent:
    SPECIFICATION_VERSION = "00"
    TRACEPARENT_REGEX = re.compile("[0-9a-f]{2}-(?!0{32})([0-9a-f]{32})-(?!0{16})([0-9a-f]{16})-[0-9a-f]{2}")

    def __init__(self):
        self.traceparent = None
        self.trace_id = None
        self.parent_id = None
        self.sampled = None

    @property
    def traceparent(self):
        return self._traceparent

    @traceparent.setter
    def traceparent(self, value):
        if value and self.TRACEPARENT_REGEX.match(value):
            self._traceparent = value
        else:
            self._traceparent = None

    @property
    def trace_id(self):
        return self._trace_id

    @trace_id.setter
    def trace_id(self, value):
        self._trace_id = value

    @property
    def parent_id(self):
        return self._parent_id

    @parent_id.setter
    def parent_id(self, value):
        self._parent_id = value

    @property
    def sampled(self):
        return self._sampled

    @sampled.setter
    def sampled(self, value):
        self._sampled = value

    def extract_traceparent(self, headers):
        """
        Extracts from the headers dict the traceparent key/value and validates the value while trying to set the
        traceparent property. If the validation succeeds all other traceparent sub-properties are getting extracted
        :param headers: dict with headers
        :return: it sets the class properties accordingly
        """
        self.traceparent = headers.get('traceparent', None)
        if self.traceparent is None:
            return

        try:
            traceparent_properties = self.traceparent.split("-")
            if traceparent_properties[0] == self.SPECIFICATION_VERSION:
                self.trace_id = traceparent_properties[1]
                self.parent_id = traceparent_properties[2]
                self.sampled = traceparent_properties[3]
            else:
                raise Exception
        except Exception:
            logger.debug("traceparent does not follow version 00 specification")

    def update_traceparent(self, in_trace_id, in_span_id, level):
        """
        This method updates the traceparent header or generates one if there was no traceparent incoming header or it
        was invalid
        :param in_trace_id: instana trace id, used when there is no preexisting trace_id from the traceparent header
        :param in_span_id: instana span id, used to update the parent id of the traceparent header
        :param level: instana level, used to determine the value of sampled flag of the traceparent header
        :return: sets the updated traceparent header
        """
        if self.trace_id is None:  # modify the trace_id part only when it was not present at all
            self.trace_id = in_trace_id.zfill(32)
        self.parent_id = in_span_id.zfill(16)
        self.sampled = "01" if level == 1 else "00"
        self.traceparent = "{version}-{traceid}-{parentid}-{sampled}".format(version=self.SPECIFICATION_VERSION,
                                                                             traceid=self.trace_id,
                                                                             parentid=self.parent_id,
                                                                             sampled=self.sampled)
