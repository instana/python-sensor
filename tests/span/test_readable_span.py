import time
from instana.span.readable_span import Event, ReadableSpan
from instana.span_context import SpanContext
from opentelemetry.trace.status import Status, StatusCode


def test_event() -> None:
    name = "sample-event"
    test_event = Event(name)

    assert test_event.name == name
    assert not test_event.attributes
    assert test_event.timestamp < time.time_ns()


def test_event_with_params() -> None:
    name = "sample-event"
    attributes = ["attribute"]
    timestamp = time.time_ns()
    test_event = Event(name, attributes, timestamp)

    assert test_event.name == name
    assert test_event.attributes == attributes
    assert test_event.timestamp == timestamp


def test_readablespan(
    span_context: SpanContext,
    trace_id: int,
    span_id: int,
) -> None:
    span_name = "test-span"
    timestamp = time.time_ns()
    span = ReadableSpan(span_name, span_context)

    assert span is not None
    assert isinstance(span, ReadableSpan)
    assert span.name == span_name

    span_context = span.context
    assert isinstance(span_context, SpanContext)
    assert span_context.trace_id == trace_id
    assert span_context.span_id == span_id

    assert span.start_time
    assert isinstance(span.start_time, int)
    assert span.start_time > timestamp
    assert not span.end_time
    assert not span.attributes
    assert not span.events
    assert not span.parent_id
    assert not span.duration
    assert span.status

    assert not span.stack
    assert span.synthetic is False


def test_readablespan_with_params(
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
    span = ReadableSpan(
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

    assert span.name == span_name
    assert span.parent_id == parent_id
    assert span.start_time == start_time
    assert span.end_time == end_time
    assert span.attributes == attributes
    assert span.events == events
    assert span.status == status
    assert span.duration == end_time - start_time
    assert span.stack == stack
