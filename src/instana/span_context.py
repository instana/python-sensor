# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import typing

from opentelemetry.trace import SpanContext as OtelSpanContext
from opentelemetry.trace.span import (
    DEFAULT_TRACE_OPTIONS,
    DEFAULT_TRACE_STATE,
    TraceFlags,
    TraceState,
    format_span_id,
)


class SpanContext(OtelSpanContext):
    """The state of a Span to propagate between processes.

    This class includes the immutable attributes of a :class:`.Span` that must
    be propagated to a span's children and across process boundaries.

    Required Args:
        trace_id: The ID of the trace that this span belongs to.
        span_id: This span's ID.
        is_remote: True if propagated from a remote parent.
    """

    def __new__(
        cls,
        trace_id: int,
        span_id: int,
        is_remote: bool,
        trace_flags: typing.Optional[TraceFlags] = DEFAULT_TRACE_OPTIONS,
        trace_state: typing.Optional[TraceState] = DEFAULT_TRACE_STATE,
        level=1,
        synthetic=False,
        trace_parent=None,  # true/false flag,
        instana_ancestor=None,
        long_trace_id=None,
        correlation_type=None,
        correlation_id=None,
        traceparent=None,  # temporary storage of the validated traceparent header of the incoming request
        tracestate=None,  # temporary storage of the tracestate header
        **kwargs,
    ) -> "SpanContext":
        instance = super().__new__(cls, trace_id, span_id, is_remote, trace_flags, trace_state)
        return tuple.__new__(
            cls,
            (
                instance.trace_id,
                instance.span_id,
                instance.is_remote,
                instance.trace_flags,
                instance.trace_state,
                instance.is_valid,
                level,
                synthetic,
                trace_parent,  # true/false flag,
                instana_ancestor,
                long_trace_id,
                correlation_type,
                correlation_id,
                traceparent,  # temporary storage of the validated traceparent header of the incoming request
                tracestate,  # temporary storage of the tracestate header
            ),
        )

    def __getnewargs__(
        self,
    ):  # -> typing.Tuple[int, int, bool, "TraceFlags", "TraceState", int, bool, bool]:
        return (
            self.trace_id,
            self.span_id,
            self.is_remote,
            self.trace_flags,
            self.trace_state,
            self.level,
            self.synthetic,
            self.trace_parent,
            self.instana_ancestor,
            self.long_trace_id,
            self.correlation_type,
            self.correlation_id,
            self.traceparent,
            self.tracestate,
        )

    @property
    def level(self) -> int:
        return self[6]

    @property
    def synthetic(self) -> bool:
        return self[7]

    @property
    def trace_parent(self) -> bool:
        return self[8]

    @property
    def instana_ancestor(self):
        return self[9]

    @property
    def long_trace_id(self):
        return self[10]

    @property
    def correlation_type(self):
        return self[11]

    @property
    def correlation_id(self):
        return self[12]

    @property
    def traceparent(self):
        return self[13]

    @property
    def tracestate(self):
        return self[14]

    @property
    def suppression(self) -> bool:
        return self.level == 0

    def __repr__(self) -> str:
        return f"{type(self).__name__}(trace_id=0x{format_span_id(self.trace_id)}, span_id=0x{format_span_id(self.span_id)}, trace_flags=0x{self.trace_flags:02x}, trace_state={self.trace_state!r}, is_remote={self.is_remote}, synthetic={self.synthetic})"
