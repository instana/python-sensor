import time
from basictracer import BasicTracer
import instana.recorder as r
import opentracing
import instana.options as o
import instana.sensor as s

from basictracer.context import SpanContext
from basictracer.span import BasicSpan
from instana.util import generate_id


class InstanaTracer(BasicTracer):
    sensor = None

    def __init__(self, options=o.Options()):
        self.sensor = s.Sensor(options)
        super(InstanaTracer, self).__init__(
            r.InstanaRecorder(self.sensor), r.InstanaSampler())

    def start_span(
            self,
            operation_name=None,
            child_of=None,
            references=None,
            tags=None,
            start_time=None):
        "Taken from BasicTracer so we can override generate_id calls to ours"

        start_time = time.time() if start_time is None else start_time

        # See if we have a parent_ctx in `references`
        parent_ctx = None
        if child_of is not None:
            parent_ctx = (
                child_of if isinstance(child_of, opentracing.SpanContext)
                else child_of.context)
        elif references is not None and len(references) > 0:
            # TODO only the first reference is currently used
            parent_ctx = references[0].referenced_context

        # Assemble the child ctx
        instana_id = generate_id()
        ctx = SpanContext(span_id=instana_id)
        if parent_ctx is not None:
            if parent_ctx._baggage is not None:
                ctx._baggage = parent_ctx._baggage.copy()
            ctx.trace_id = parent_ctx.trace_id
            ctx.sampled = parent_ctx.sampled
        else:
            ctx.trace_id = instana_id
            ctx.sampled = self.sampler.sampled(ctx.trace_id)

        # Tie it all together
        return BasicSpan(
            self,
            operation_name=operation_name,
            context=ctx,
            parent_id=(None if parent_ctx is None else parent_ctx.span_id),
            tags=tags,
            start_time=start_time)


def init(options):
    opentracing.tracer = InstanaTracer(options)
