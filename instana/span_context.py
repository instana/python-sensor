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
            synthetic=False):

        self.level = level
        self.trace_id = trace_id
        self.span_id = span_id
        self.sampled = sampled
        self.synthetic = synthetic
        self._baggage = baggage or {}

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