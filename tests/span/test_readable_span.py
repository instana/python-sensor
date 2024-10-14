# (c) Copyright IBM Corp. 2024

import time
from typing import Generator

import pytest
from opentelemetry.trace.status import Status, StatusCode

from instana.span.readable_span import Event, ReadableSpan
from instana.span_context import SpanContext


class TestReadableSpan:
    @pytest.fixture(autouse=True)
    def _resource(
        self,
    ) -> Generator[None, None, None]:
        self.span = None
        yield

    def test_readablespan(
        self,
        span_context: SpanContext,
        trace_id: int,
        span_id: int,
    ) -> None:
        span_name = "test-span"
        timestamp = time.time_ns()
        self.span = ReadableSpan(span_name, span_context)

        assert self.span is not None
        assert isinstance(self.span, ReadableSpan)
        assert self.span.name == span_name

        span_context = self.span.context
        assert isinstance(span_context, SpanContext)
        assert span_context.trace_id == trace_id
        assert span_context.span_id == span_id

        assert self.span.start_time
        assert isinstance(self.span.start_time, int)
        assert self.span.start_time > timestamp
        assert not self.span.end_time
        assert not self.span.attributes
        assert not self.span.events
        assert not self.span.parent_id
        assert not self.span.duration
        assert self.span.status

        assert not self.span.stack
        assert self.span.synthetic is False

    def test_readablespan_with_params(
        self,
        span_context: SpanContext,
    ) -> None:
        span_name = "test-span"
        parent_id = "123456789"
        start_time = time.time_ns()
        end_time = time.time_ns()
        attributes = {"key": "value"}
        event_name = "event"
        events = [Event(event_name, attributes, start_time)]
        status = Status(StatusCode.OK)
        stack = ["span-1", "span-2"]
        self.span = ReadableSpan(
            span_name,
            span_context,
            parent_id,
            start_time,
            end_time,
            attributes,
            events,
            status,
            stack,
        )

        assert self.span.name == span_name
        assert self.span.parent_id == parent_id
        assert self.span.start_time == start_time
        assert self.span.end_time == end_time
        assert self.span.attributes == attributes
        assert self.span.events == events
        assert self.span.status == status
        assert self.span.duration == end_time - start_time
        assert self.span.stack == stack
