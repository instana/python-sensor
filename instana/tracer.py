from __future__ import absolute_import

import os
import re
import time
import traceback

import opentracing as ot
from basictracer import BasicTracer

from .util.ids import generate_id
from .span_context import SpanContext
from .span import InstanaSpan, RegisteredSpan
from .recorder import StanRecorder, InstanaSampler
from .propagators.http_propagator import HTTPPropagator
from .propagators.text_propagator import TextPropagator
from .propagators.binary_propagator import BinaryPropagator


class InstanaTracer(BasicTracer):
    def __init__(self, scope_manager=None, recorder=None):

        if recorder is None:
            recorder = StanRecorder()

        super(InstanaTracer, self).__init__(
            recorder, InstanaSampler(), scope_manager)

        self._propagators[ot.Format.HTTP_HEADERS] = HTTPPropagator()
        self._propagators[ot.Format.TEXT_MAP] = TextPropagator()
        self._propagators[ot.Format.BINARY] = BinaryPropagator()

    def start_active_span(self,
                          operation_name,
                          child_of=None,
                          references=None,
                          tags=None,
                          start_time=None,
                          ignore_active_span=False,
                          finish_on_close=True):

        # create a new Span
        span = self.start_span(
            operation_name=operation_name,
            child_of=child_of,
            references=references,
            tags=tags,
            start_time=start_time,
            ignore_active_span=ignore_active_span,
        )

        return self.scope_manager.activate(span, finish_on_close)

    def start_span(self,
                   operation_name=None,
                   child_of=None,
                   references=None,
                   tags=None,
                   start_time=None,
                   ignore_active_span=False):
        "Taken from BasicTracer so we can override generate_id calls to ours"

        start_time = time.time() if start_time is None else start_time

        # See if we have a parent_ctx in `references`
        parent_ctx = None
        if child_of is not None:
            parent_ctx = (
                child_of if isinstance(child_of, SpanContext)
                else child_of.context)
        elif references is not None and len(references) > 0:
            # TODO only the first reference is currently used
            parent_ctx = references[0].referenced_context

        # retrieve the active SpanContext
        if not ignore_active_span and parent_ctx is None:
            scope = self.scope_manager.active
            if scope is not None:
                parent_ctx = scope.span.context

        # Assemble the child ctx
        gid = generate_id()
        ctx = SpanContext(span_id=gid)
        if parent_ctx is not None and parent_ctx.trace_id is not None:
            if hasattr(parent_ctx, '_baggage') and parent_ctx._baggage is not None:
                ctx._baggage = parent_ctx._baggage.copy()
            ctx.trace_id = parent_ctx.trace_id
            ctx.sampled = parent_ctx.sampled
        else:
            ctx.trace_id = gid
            ctx.sampled = self.sampler.sampled(ctx.trace_id)

        # Tie it all together
        span = InstanaSpan(self,
                           operation_name=operation_name,
                           context=ctx,
                           parent_id=(None if parent_ctx is None else parent_ctx.span_id),
                           tags=tags,
                           start_time=start_time)

        if parent_ctx is not None:
            span.synthetic = parent_ctx.synthetic

        if operation_name in RegisteredSpan.EXIT_SPANS:
            self.__add_stack(span)

        elif operation_name in RegisteredSpan.ENTRY_SPANS:
            # For entry spans, add only a backtrace fingerprint
            self.__add_stack(span, limit=2)

        return span

    def inject(self, span_context, format, carrier):
        if format in self._propagators:
            return self._propagators[format].inject(span_context, carrier)

        raise ot.UnsupportedFormatException()

    def extract(self, format, carrier):
        if format in self._propagators:
            return self._propagators[format].extract(carrier)

        raise ot.UnsupportedFormatException()

    def __add_stack(self, span, limit=None):
        """ Adds a backtrace to this span """
        span.stack = []
        frame_count = 0

        tb = traceback.extract_stack()
        tb.reverse()
        for frame in tb:
            if limit is not None and frame_count >= limit:
                break

            # Exclude Instana frames unless we're in dev mode
            if "INSTANA_DEBUG" not in os.environ:
                if re_tracer_frame.search(frame[0]) is not None:
                    continue

                if re_with_stan_frame.search(frame[2]) is not None:
                    continue

            span.stack.append({
                "c": frame[0],
                "n": frame[1],
                "m": frame[2]
            })

            if limit is not None:
                frame_count += 1


# Used by __add_stack
re_tracer_frame = re.compile(r"/instana/.*\.py$")
re_with_stan_frame = re.compile('with_instana')
