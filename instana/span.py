from basictracer.span import BasicSpan
from basictracer.context import SpanContext


class InstanaSpan(BasicSpan):
    def finish(self, finish_time=None):
        super(InstanaSpan, self).finish(finish_time)
