# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016


import os
import re
import time
import traceback
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator, Mapping, Optional, Type, Union

from opentelemetry.context.context import Context
from opentelemetry.trace import (
    SpanKind,
    TraceFlags,
    Tracer,
    TracerProvider,
    _Links,
    use_span,
)
from opentelemetry.util import types

from instana.agent.host import HostAgent
from instana.log import logger
from instana.propagators.binary_propagator import BinaryPropagator
from instana.propagators.exceptions import UnsupportedFormatException
from instana.propagators.format import Format
from instana.propagators.http_propagator import HTTPPropagator
from instana.propagators.kafka_propagator import KafkaPropagator
from instana.propagators.text_propagator import TextPropagator
from instana.recorder import StanRecorder
from instana.sampling import InstanaSampler, Sampler
from instana.span.kind import EXIT_SPANS
from instana.span.span import InstanaSpan, get_current_span
from instana.span_context import SpanContext
from instana.util.ids import generate_id

if TYPE_CHECKING:
    from instana.agent.base import BaseAgent
    from instana.propagators.base_propagator import BasePropagator, CarrierT


class InstanaTracerProvider(TracerProvider):
    def __init__(
        self,
        sampler: Optional[Sampler] = None,
        span_processor: Optional[StanRecorder] = None,
        exporter: Optional[Type["BaseAgent"]] = None,
    ) -> None:
        self.sampler = sampler or InstanaSampler()
        self._span_processor = span_processor or StanRecorder()
        self._exporter = exporter or HostAgent()
        self._propagators = {}
        self._propagators[Format.HTTP_HEADERS] = HTTPPropagator()
        self._propagators[Format.TEXT_MAP] = TextPropagator()
        self._propagators[Format.BINARY] = BinaryPropagator()
        self._propagators[Format.KAFKA_HEADERS] = KafkaPropagator()

    def get_tracer(
        self,
        instrumenting_module_name: str,
        instrumenting_library_version: Optional[str] = None,
        schema_url: Optional[str] = None,
        attributes: Optional[types.Attributes] = None,
    ) -> Tracer:
        if not instrumenting_module_name:  # Reject empty strings too.
            instrumenting_module_name = ""
            logger.error("get_tracer called with missing module name.")

        return InstanaTracer(
            self.sampler,
            self._span_processor,
            self._exporter,
            self._propagators,
        )

    def add_span_processor(
        self,
        span_processor: StanRecorder,
    ) -> None:
        """Registers a new SpanProcessor for the TracerProvider."""
        self._span_processor = span_processor


class InstanaTracer(Tracer):
    """Handles :class:`InstanaSpan` creation and in-process context propagation.

    This class provides methods for manipulating the context, creating spans,
    and controlling spans' lifecycles.
    """

    def __init__(
        self,
        sampler: Sampler,
        span_processor: StanRecorder,
        exporter: Type["BaseAgent"],
        propagators: Mapping[str, Type["BasePropagator"]],
    ) -> None:
        self._sampler = sampler
        self._span_processor = span_processor
        self._exporter = exporter
        self._propagators = propagators

    @property
    def span_processor(self) -> Optional[StanRecorder]:
        return self._span_processor

    @property
    def exporter(self) -> Optional[Type["BaseAgent"]]:
        return self._exporter

    def start_span(
        self,
        name: str,
        span_context: Optional[SpanContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: types.Attributes = None,
        links: _Links = None,
        start_time: Optional[int] = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ) -> InstanaSpan:
        parent_context = (
            span_context if span_context else get_current_span().get_span_context()
        )

        if parent_context and not isinstance(parent_context, SpanContext):
            raise TypeError("parent_context must be an Instana SpanContext or None.")

        span_context = self._create_span_context(parent_context)
        span = InstanaSpan(
            name,
            span_context,
            self._span_processor,
            parent_id=(None if parent_context is None else parent_context.span_id),
            start_time=(time.time_ns() if start_time is None else start_time),
            attributes=attributes,
            # events: Sequence[Event] = None,
        )

        if name in EXIT_SPANS:
            self._add_stack(span)

        return span

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        span_context: Optional[SpanContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: types.Attributes = None,
        links: _Links = None,
        start_time: Optional[int] = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        end_on_exit: bool = True,
    ) -> Iterator[InstanaSpan]:
        span = self.start_span(
            name=name,
            span_context=span_context,
            kind=kind,
            attributes=attributes,
            links=links,
            start_time=start_time,
            record_exception=record_exception,
            set_status_on_exception=set_status_on_exception,
        )
        with use_span(
            span,
            end_on_exit=end_on_exit,
            record_exception=record_exception,
            set_status_on_exception=set_status_on_exception,
        ) as span:
            yield span

    def _add_stack(self, span: InstanaSpan, limit: Optional[int] = 30) -> None:
        """
        Adds a backtrace to <span>.  The default length limit for
        stack traces is 30 frames.  A hard limit of 40 frames is enforced.
        """
        try:
            sanitized_stack = []
            if limit > 40:
                limit = 40

            trace_back = traceback.extract_stack()
            trace_back.reverse()
            for frame in trace_back:
                # Exclude Instana frames unless we're in dev mode
                if "INSTANA_DEBUG" not in os.environ:
                    if re_tracer_frame.search(frame[0]) is not None:
                        continue

                    if re_with_stan_frame.search(frame[2]) is not None:
                        continue

                sanitized_stack.append({"c": frame[0], "n": frame[1], "m": frame[2]})

            if len(sanitized_stack) > limit:
                # (limit * -1) gives us negative form of <limit> used for
                # slicing from the end of the list. e.g. stack[-30:]
                span.stack = sanitized_stack[(limit * -1) :]
            else:
                span.stack = sanitized_stack
        except Exception:
            # No fail
            pass

    def _create_span_context(self, parent_context: SpanContext) -> SpanContext:
        """Creates a new SpanContext based on the given parent context."""

        if parent_context and parent_context.is_valid:
            trace_id = parent_context.trace_id
            span_id = generate_id()
            trace_flags = parent_context.trace_flags
            is_remote = parent_context.is_remote
        else:
            trace_id = span_id = generate_id()
            trace_flags = TraceFlags(self._sampler.sampled())
            is_remote = False

        span_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            trace_flags=trace_flags,
            is_remote=is_remote,
            level=(parent_context.level if parent_context else 1),
            synthetic=(parent_context.synthetic if parent_context else False),
            trace_parent=(parent_context.trace_parent if parent_context else None),
            instana_ancestor=(
                parent_context.instana_ancestor if parent_context else None
            ),
            long_trace_id=(parent_context.long_trace_id if parent_context else None),
            correlation_type=(
                parent_context.correlation_type if parent_context else None
            ),
            correlation_id=(parent_context.correlation_id if parent_context else None),
            traceparent=(parent_context.traceparent if parent_context else None),
            tracestate=(parent_context.tracestate if parent_context else None),
        )

        return span_context

    def inject(
        self,
        span_context: SpanContext,
        format: Union[
            Format.BINARY, Format.HTTP_HEADERS, Format.TEXT_MAP, Format.KAFKA_HEADERS  # type: ignore
        ],
        carrier: "CarrierT",
        disable_w3c_trace_context: bool = False,
    ) -> Optional["CarrierT"]:
        if format in self._propagators:
            return self._propagators[format].inject(
                span_context, carrier, disable_w3c_trace_context
            )

        raise UnsupportedFormatException()

    def extract(
        self,
        format: Union[
            Format.BINARY, Format.HTTP_HEADERS, Format.TEXT_MAP, Format.KAFKA_HEADERS  # type: ignore
        ],
        carrier: "CarrierT",
        disable_w3c_trace_context: bool = False,
    ) -> Optional[Context]:
        if format in self._propagators:
            return self._propagators[format].extract(carrier, disable_w3c_trace_context)

        raise UnsupportedFormatException()


# Used by __add_stack
re_tracer_frame = re.compile(r"/instana/.*\.py$")
re_with_stan_frame = re.compile("with_instana")
