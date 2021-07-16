# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021
from ..log import logger


class Trancestate:
    def __init__(self):
        self.tracestate = None

    @property
    def tracestate(self):
        return self._tracestate

    @tracestate.setter
    def tracestate(self, value):
        self._tracestate = value

    def extract_tracestate(self, headers):
        self.tracestate = headers.get('tracestate', None)
        if self.tracestate is None:
            return None

        return self.tracestate
