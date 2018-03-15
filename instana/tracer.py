import time
from basictracer import BasicTracer
import instana.recorder as r
import opentracing as ot
import instana
import instana.options as o

from instana.util import generate_id
from instana.span import InstanaSpan
from basictracer.context import SpanContext
from instana.http_propagator import HTTPPropagator
from instana.text_propagator import TextPropagator


class InstanaTracer(BasicTracer):
    sensor = None
    cur_ctx = None

    def __init__(self, options=o.Options()):
        self.sensor = instana.global_sensor
        super(InstanaTracer, self).__init__(
            r.InstanaRecorder(self.sensor), r.InstanaSampler())

        self._propagators[ot.Format.HTTP_HEADERS] = HTTPPropagator()
        self._propagators[ot.Format.TEXT_MAP] = TextPropagator()

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
                child_of if isinstance(child_of, ot.SpanContext)
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
        span = InstanaSpan(
            self,
            operation_name=operation_name,
            context=ctx,
            parent_id=(None if parent_ctx is None else parent_ctx.span_id),
            tags=tags,
            start_time=start_time)

        self.cur_ctx = span.context
        return span

    def current_context(self):
        context = None
        if self.cur_ctx is not None:
            context = self.cur_ctx
        return context

    def inject(self, span_context, format, carrier):
        if format in self._propagators:
            self._propagators[format].inject(span_context, carrier)
        else:
            raise ot.UnsupportedFormatException()

    def extract(self, format, carrier):
        if format in self._propagators:
            return self._propagators[format].extract(carrier)
        else:
            raise ot.UnsupportedFormatException()

    def handle_fork(self):
        self.sensor.handle_fork()
        self.recorder = r.InstanaRecorder(self.sensor)


def init(options):
    """
    Deprecated.
        No longer in use.
        To be removed in next major release.
    """
    return instana.internal_tracer
