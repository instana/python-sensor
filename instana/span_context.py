
from basictracer.context import SpanContext


class InstanaSpanContext(SpanContext):
    """
    SpanContext based on the Basic tracer implementation.
    We subclass this so that we can also store 'level' and eventually
    remove the basictracer dependency altogether.
    """
    def __init__(
            self,
            trace_id=None,
            span_id=None,
            baggage=None,
            sampled=True,
            level=1):
        self.level = level

        super(InstanaSpanContext, self).__init__(trace_id, span_id, baggage, sampled)


