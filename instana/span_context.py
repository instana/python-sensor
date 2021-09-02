# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


class SpanContext():
    def __init__(
            self,
            trace_id=None,
            span_id=None,
            baggage=None,
            sampled=True,
            level=1,
            synthetic=False
    ):

        self.level = level
        self.trace_id = trace_id
        self.span_id = span_id
        self.sampled = sampled
        self.synthetic = synthetic
        self._baggage = baggage or {}

        self.trace_parent = None  # true/false flag
        self.instana_ancestor = None
        self.long_trace_id = None
        self.correlation_type = None
        self.correlation_id = None
        self.traceparent = None  # temporary storage of the validated traceparent header of the incoming request
        self.tracestate = None  # temporary storage of the tracestate header

    @property
    def traceparent(self):
        return self._traceparent

    @traceparent.setter
    def traceparent(self, value):
        self._traceparent = value

    @property
    def tracestate(self):
        return self._tracestate

    @tracestate.setter
    def tracestate(self, value):
        self._tracestate = value

    @property
    def trace_parent(self):
        return self._trace_parent

    @trace_parent.setter
    def trace_parent(self, value):
        self._trace_parent = value

    @property
    def instana_ancestor(self):
        return self._instana_ancestor

    @instana_ancestor.setter
    def instana_ancestor(self, value):
        self._instana_ancestor = value

    @property
    def long_trace_id(self):
        return self._long_trace_id

    @long_trace_id.setter
    def long_trace_id(self, value):
        self._long_trace_id = value

    @property
    def correlation_type(self):
        return self._correlation_type

    @correlation_type.setter
    def correlation_type(self, value):
        self._correlation_type = value

    @property
    def correlation_id(self):
        return self._correlation_id

    @correlation_id.setter
    def correlation_id(self, value):
        self._correlation_id = value

    @property
    def baggage(self):
        return self._baggage

    def with_baggage_item(self, key, value):
        new_baggage = self._baggage.copy()
        new_baggage[key] = value
        return SpanContext(
            trace_id=self.trace_id,
            span_id=self.span_id,
            sampled=self.sampled,
            baggage=new_baggage)