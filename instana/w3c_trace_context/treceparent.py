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
        self.traceparent = headers.get('traceparent', None)
        if self.traceparent is None:
            return None

        try:
            traceparent_properties = self.traceparent.split("-")
            if traceparent_properties[0] == self.SPECIFICATION_VERSION:
                self.trace_id = traceparent_properties[1]
                self.parent_id = traceparent_properties[2]
                self.sampled = traceparent_properties[3]
            else:
                raise Exception
        except Exception:
            logger.debug("traceparent does follow version 00 specification")
            return None

        return self.traceparent

    def update_traceparent(self, in_trace_id, in_span_id, level):
        if self.trace_id is None:  # modify the trace_id part only when it was not present at all
            self.trace_id = in_trace_id.zfill(32)
        self.parent_id = in_span_id.zfill(16)
        self.sampled = "01" if level == 1 else "00"
        self.traceparent = "{version}-{traceid}-{parentid}-{sampled}".format(version=self.SPECIFICATION_VERSION,
                                                                             traceid=self.trace_id,
                                                                             parentid=self.parent_id,
                                                                             sampled=self.sampled)
