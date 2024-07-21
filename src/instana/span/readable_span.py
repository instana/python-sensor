# (c) Copyright IBM Corp. 2024

from time import time_ns
from typing import Optional, Sequence, List

from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.util import types

from instana.span_context import SpanContext


class Event:
    def __init__(
        self,
        name: str,
        attributes: types.Attributes = None,
        timestamp: Optional[int] = None,
    ) -> None:
        self._name = name
        self._attributes = attributes
        if timestamp is None:
            self._timestamp = time_ns()
        else:
            self._timestamp = timestamp

    @property
    def name(self) -> str:
        return self._name

    @property
    def timestamp(self) -> int:
        return self._timestamp

    @property
    def attributes(self) -> types.Attributes:
        return self._attributes


class ReadableSpan:
    """
    Provides read-only access to span attributes.

    Users should NOT be creating these objects directly.
    `ReadableSpan`s are created as a direct result from using the tracing pipeline
    via the `Tracer`.
    """

    def __init__(
        self,
        name: str,
        context: SpanContext,
        parent_id: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        attributes: types.Attributes = {},
        events: Sequence[Event] = [],
        status: Optional[Status] = Status(StatusCode.UNSET),
        stack: Optional[List] = None,
    ) -> None:
        self._name = name
        self._context = context
        self._start_time = start_time or time_ns()
        self._end_time = end_time
        self._duration = (
            self._end_time - self._start_time
            if self._start_time and self._end_time
            else None
        )
        self._attributes = attributes if attributes else {}
        self._events = events
        self._parent_id = parent_id
        self._status = status
        self.stack = stack
        self.synthetic = False
        if context.synthetic:
            self.synthetic = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def context(self) -> SpanContext:
        return self._context

    @property
    def start_time(self) -> Optional[int]:
        return self._start_time

    @property
    def end_time(self) -> Optional[int]:
        return self._end_time

    @property
    def duration(self) -> Optional[int]:
        return self._duration

    @property
    def attributes(self) -> types.Attributes:
        return self._attributes

    @property
    def events(self) -> Sequence[Event]:
        return self._events

    @property
    def status(self) -> Status:
        return self._status

    @property
    def parent_id(self) -> int:
        return self._parent_id
