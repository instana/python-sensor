from basictracer.span import BasicSpan
from basictracer.context import SpanContext


class InstanaSpan(BasicSpan):
    def finish(self, finish_time=None):
        if self.parent_id is None:
            self.tracer.cur_ctx = None
        else:
            # Set tracer context to the parent span
            pctx = SpanContext(span_id=self.parent_id,
                               trace_id=self.context.trace_id,
                               baggage={},
                               sampled=True)
            self.tracer.cur_ctx = pctx
        super(InstanaSpan, self).finish(finish_time)
