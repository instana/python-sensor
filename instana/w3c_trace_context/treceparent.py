# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from ..log import logger


class Traceparent:
    SPECIFICATION_VERSION = "00"

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
        self._traceparent = value

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

    def extract_tranparent(self, headers):
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

        # Value = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
