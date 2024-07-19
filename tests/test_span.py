# (c) Copyright IBM Corp. 2024

import time
from unittest.mock import patch

import pytest
from opentelemetry.trace.status import Status, StatusCode

from instana.recorder import StanRecorder
from instana.span.span import INVALID_SPAN, Event, InstanaSpan, get_current_span
from instana.span_context import SpanContext


def test_span_default(
    span_context: SpanContext,
    span_processor: StanRecorder,
    trace_id: int,
    span_id: int,
) -> None:
    span_name = "test-span"
    timestamp = time.time_ns()
    span = InstanaSpan(span_name, span_context, span_processor)

    assert span is not None
    assert isinstance(span, InstanaSpan)
    assert span.name == span_name

    context = span.context
    assert isinstance(context, SpanContext)
    assert context.trace_id == trace_id
    assert context.span_id == span_id

    assert span.start_time
    assert isinstance(span.start_time, int)
    assert span.start_time > timestamp
    assert not span.end_time
    assert not span.attributes
    assert not span.events
    assert span.is_recording()
    assert span.status
    assert span.status.is_unset


def test_span_get_span_context(
    span_context: SpanContext,
    span_processor: StanRecorder,
    trace_id: int,
    span_id: int,
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    context = span.get_span_context()
    assert isinstance(context, SpanContext)
    assert context.trace_id == trace_id
    assert context.span_id == span_id
    assert context == span.context


def test_span_set_attributes_default(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert not span.attributes

    attributes = {
        "field1": 1,
        "field2": "two",
    }
    span.set_attributes(attributes)

    assert span.attributes
    assert len(span.attributes) == 2
    assert "field1" in span.attributes.keys()
    assert "two" == span.attributes.get("field2")


def test_span_set_attributes(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    attributes = {
        "field1": 1,
        "field2": "two",
    }
    span = InstanaSpan(span_name, span_context, span_processor, attributes=attributes)

    assert span.attributes
    assert len(span.attributes) == 2
    assert "field1" in span.attributes.keys()
    assert "two" == span.attributes.get("field2")

    attributes = {
        "field3": True,
        "field4": ["four", "vier", "quatro"],
    }
    span.set_attributes(attributes)

    assert len(span.attributes) == 4
    assert "field3" in span.attributes.keys()
    assert "vier" in span.attributes.get("field4")


def test_span_set_attribute_default(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert not span.attributes

    attributes = {
        "field1": 1,
        "field2": "two",
    }
    for key, value in attributes.items():
        span.set_attribute(key, value)

    assert span.attributes
    assert len(span.attributes) == 2
    assert "field1" in span.attributes.keys()
    assert "two" == span.attributes.get("field2")


def test_span_set_attribute(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    attributes = {
        "field1": 1,
        "field2": "two",
    }
    span = InstanaSpan(span_name, span_context, span_processor, attributes=attributes)

    assert span.attributes
    assert len(span.attributes) == 2
    assert "field1" in span.attributes.keys()
    assert "two" == span.attributes.get("field2")

    attributes = {
        "field3": True,
        "field4": ["four", "vier", "quatro"],
    }
    for key, value in attributes.items():
        span.set_attribute(key, value)

    assert len(span.attributes) == 4
    assert "field3" in span.attributes.keys()
    assert "vier" in span.attributes.get("field4")


def test_span_update_name(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span-1"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert span is not None
    assert isinstance(span, InstanaSpan)
    assert span.name == span_name

    new_span_name = "test-span-2"
    span.update_name(new_span_name)
    assert span is not None
    assert isinstance(span, InstanaSpan)
    assert span.name == new_span_name


def test_span_set_status_with_Status_default(
    span_context: SpanContext, span_processor: StanRecorder, caplog
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert span.status
    assert span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code == StatusCode.UNSET
    assert span.status.status_code != StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR

    status_desc = "Status is OK."
    span_status = Status(status_code=StatusCode.OK, description=status_desc)

    assert (
        "description should only be set when status_code is set to StatusCode.ERROR"
        == caplog.record_tuples[0][2]
    )

    span.set_status(span_status)

    assert span.status
    assert not span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code == StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR


def test_span_set_status_with_Status_and_desc(
    span_context: SpanContext, span_processor: StanRecorder, caplog
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert span.status
    assert span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code == StatusCode.UNSET
    assert span.status.status_code != StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR

    status_desc = "Status is OK."
    span_status = Status(status_code=StatusCode.OK, description=status_desc)

    assert (
        "description should only be set when status_code is set to StatusCode.ERROR"
        == caplog.record_tuples[0][2]
    )

    set_status_desc = "Test"
    span.set_status(span_status, set_status_desc)
    excepted_log = f"Description {set_status_desc} ignored. Use either `Status` or `(StatusCode, Description)`"

    assert span.status
    assert not span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert excepted_log == caplog.record_tuples[1][2]
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code == StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR


def test_span_set_status_with_StatusUNSET_to_StatusERROR(
    span_context: SpanContext, span_processor: StanRecorder, caplog
) -> None:
    span_name = "test-span"
    status_desc = "Status is UNSET."
    span_status = Status(status_code=StatusCode.UNSET, description=status_desc)

    assert (
        "description should only be set when status_code is set to StatusCode.ERROR"
        == caplog.record_tuples[0][2]
    )

    span = InstanaSpan(span_name, span_context, span_processor, status=span_status)

    assert span.status
    assert span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code == StatusCode.UNSET
    assert span.status.status_code != StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR

    status_desc = "Houston we have a problem!"
    span_status = Status(StatusCode.ERROR, status_desc)
    span.set_status(span_status)

    assert span.status
    assert not span.status.is_unset
    assert not span.status.is_ok
    assert span.status.description == status_desc
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code != StatusCode.OK
    assert span.status.status_code == StatusCode.ERROR


def test_span_set_status_with_StatusOK_to_StatusERROR(
    span_context: SpanContext, span_processor: StanRecorder, caplog
) -> None:
    span_name = "test-span"
    status_desc = "Status is OK."
    span_status = Status(status_code=StatusCode.OK, description=status_desc)

    assert (
        "description should only be set when status_code is set to StatusCode.ERROR"
        == caplog.record_tuples[0][2]
    )

    span = InstanaSpan(span_name, span_context, span_processor, status=span_status)

    assert span.status
    assert not span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code == StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR

    status_desc = "Houston we have a problem!"
    span_status = Status(StatusCode.ERROR, status_desc)
    span.set_status(span_status)

    assert span.status
    assert not span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code == StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR


def test_span_set_status_with_StatusCode_default(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert span.status
    assert span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code == StatusCode.UNSET
    assert span.status.status_code != StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR

    span_status_code = StatusCode(StatusCode.OK)

    span.set_status(span_status_code)

    assert span.status
    assert not span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code == StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR


def test_span_set_status_with_StatusCode_and_desc(
    span_context: SpanContext, span_processor: StanRecorder, caplog
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert span.status
    assert span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code == StatusCode.UNSET
    assert span.status.status_code != StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR

    status_desc = "Status is OK."
    span_status_code = StatusCode(StatusCode.OK)
    span.set_status(span_status_code, status_desc)

    assert span.status
    assert not span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code == StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR
    assert (
        "description should only be set when status_code is set to StatusCode.ERROR"
        == caplog.record_tuples[0][2]
    )


def test_span_set_status_with_StatusCodeUNSET_to_StatusCodeERROR(
    span_context: SpanContext, span_processor: StanRecorder, caplog
) -> None:
    span_name = "test-span"
    status_desc = "Status is UNSET."
    span_status = Status(status_code=StatusCode.UNSET, description=status_desc)

    assert (
        "description should only be set when status_code is set to StatusCode.ERROR"
        == caplog.record_tuples[0][2]
    )

    span = InstanaSpan(span_name, span_context, span_processor, status=span_status)

    assert span.status
    assert span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code == StatusCode.UNSET
    assert span.status.status_code != StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR

    status_desc = "Houston we have a problem!"
    span_status_code = StatusCode(StatusCode.ERROR)
    span.set_status(span_status_code, status_desc)

    assert span.status
    assert not span.status.is_unset
    assert not span.status.is_ok
    assert span.status.description == status_desc
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code != StatusCode.OK
    assert span.status.status_code == StatusCode.ERROR


def test_span_set_status_with_StatusCodeOK_to_StatusCodeERROR(
    span_context: SpanContext, span_processor: StanRecorder, caplog
) -> None:
    span_name = "test-span"
    status_desc = "Status is OK."
    span_status = Status(status_code=StatusCode.OK, description=status_desc)

    assert (
        "description should only be set when status_code is set to StatusCode.ERROR"
        == caplog.record_tuples[0][2]
    )

    span = InstanaSpan(span_name, span_context, span_processor, status=span_status)

    assert span.status
    assert not span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code == StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR

    status_desc = "Houston we have a problem!"
    span_status_code = StatusCode(StatusCode.ERROR)
    span.set_status(span_status_code, status_desc)

    assert span.status
    assert not span.status.is_unset
    assert span.status.is_ok
    assert not span.status.description
    assert span.status.status_code != StatusCode.UNSET
    assert span.status.status_code == StatusCode.OK
    assert span.status.status_code != StatusCode.ERROR


def test_span_add_event_default(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert not span.events

    event_name = "event1"
    attributes = {
        "field1": 1,
        "field2": "two",
    }
    timestamp = time.time_ns()
    span.add_event(event_name, attributes, timestamp)

    assert span.events
    assert len(span.events) == 1
    for event in span.events:
        assert isinstance(event, Event)
        assert event.name == event_name
        assert event.timestamp == timestamp
        assert len(event.attributes) == 2


def test_span_add_event(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    event_name1 = "event1"
    attributes = {
        "field1": 1,
        "field2": "two",
    }
    timestamp1 = time.time_ns()
    event = Event(event_name1, attributes, timestamp1)
    span = InstanaSpan(span_name, span_context, span_processor, events=[event])

    assert span.events
    assert len(span.events) == 1
    for event in span.events:
        assert isinstance(event, Event)
        assert event.name == event_name1
        assert event.timestamp == timestamp1
        assert len(event.attributes) == 2

    event_name2 = "event2"
    attributes = {
        "field3": True,
        "field4": ["four", "vier", "quatro"],
    }
    timestamp2 = time.time_ns()
    span.add_event(event_name2, attributes, timestamp2)

    assert len(span.events) == 2
    for event in span.events:
        assert isinstance(event, Event)
        assert event.name in [event_name1, event_name2]
        assert event.timestamp in [timestamp1, timestamp2]
        assert len(event.attributes) == 2


@pytest.mark.parametrize(
    "span_name, span_attribute",
    [
        ("test-span", None),
        ("rpc-server", "rpc.error"),
        ("rpc-client", "rpc.error"),
        ("mysql", "mysql.error"),
        ("postgres", "pg.error"),
        ("django", "http.error"),
        ("http", "http.error"),
        ("urllib3", "http.error"),
        ("wsgi", "http.error"),
        ("asgi", "http.error"),
        ("celery-client", "error"),
        ("celery-worker", "error"),
        ("sqlalchemy", "sqlalchemy.err"),
        ("aws.lambda.entry", "lambda.error"),
    ],
)
def test_span_record_exception_default(
    span_context: SpanContext,
    span_processor: StanRecorder,
    span_name: str,
    span_attribute: str,
) -> None:
    exception_msg = "Test Exception"

    exception = Exception(exception_msg)
    span = InstanaSpan(span_name, span_context, span_processor)

    span.record_exception(exception)

    assert span_name == span.name
    assert 1 == span.attributes.get("ec", 0)
    if span_attribute:
        assert span_attribute in span.attributes.keys()
        assert exception_msg == span.attributes.get(span_attribute, None)
    else:
        event = span.events[-1]  # always get the latest event
        assert isinstance(event, Event)
        assert "exception" == event.name
        assert exception_msg == event.attributes.get("message", None)


def test_span_record_exception_with_attribute(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    exception_msg = "Test Exception"
    attributes = {
        "custom_attr": 0,
    }

    exception = Exception(exception_msg)
    span = InstanaSpan(span_name, span_context, span_processor)

    span.record_exception(exception, attributes)

    assert span_name == span.name
    assert 1 == span.attributes.get("ec", 0)

    event = span.events[-1]  # always get the latest event
    assert isinstance(event, Event)
    assert 2 == len(event.attributes)
    assert exception_msg == event.attributes.get("message", None)
    assert 0 == event.attributes.get("custom_attr", None)


def test_span_record_exception_with_Exception_msg(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "wsgi"
    span_attribute = "http.error"
    exception_msg = "Test Exception"

    exception = Exception()
    exception.message = exception_msg
    span = InstanaSpan(span_name, span_context, span_processor)

    span.record_exception(exception)

    assert span_name == span.name
    assert 1 == span.attributes.get("ec", 0)
    assert span_attribute in span.attributes.keys()
    assert exception_msg == span.attributes.get(span_attribute, None)


def test_span_record_exception_with_Exception_none_msg(
    span_context: SpanContext,
    span_processor: StanRecorder,
) -> None:
    span_name = "wsgi"
    span_attribute = "http.error"

    exception = Exception()
    exception.message = None
    span = InstanaSpan(span_name, span_context, span_processor)

    span.record_exception(exception)

    assert span_name == span.name
    assert 1 == span.attributes.get("ec", 0)
    assert span_attribute in span.attributes.keys()
    assert "Exception()" == span.attributes.get(span_attribute, None)


def test_span_record_exception_with_Exception_raised(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"

    exception = None
    span = InstanaSpan(span_name, span_context, span_processor)

    with patch(
        "instana.span.span.InstanaSpan.add_event", side_effect=Exception("mocked error")
    ):
        with pytest.raises(Exception):
            span.record_exception(exception)


def test_span_end_default(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert not span.end_time

    span.end()

    assert span.end_time
    assert isinstance(span.end_time, int)


def test_span_end(span_context: SpanContext, span_processor: StanRecorder) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    assert not span.end_time

    timestamp_end = time.time_ns()
    span.end(timestamp_end)

    assert span.end_time
    assert span.end_time == timestamp_end


def test_span_mark_as_errored_default(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    attributes = {
        "ec": 0,
    }
    span = InstanaSpan(span_name, span_context, span_processor, attributes=attributes)

    assert span.attributes
    assert len(span.attributes) == 1
    assert span.attributes.get("ec") == 0

    span.mark_as_errored()

    assert span.attributes
    assert len(span.attributes) == 1
    assert span.attributes.get("ec") == 1


def test_span_mark_as_errored(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    attributes = {
        "ec": 0,
    }
    span = InstanaSpan(span_name, span_context, span_processor, attributes=attributes)

    assert span.attributes
    assert len(span.attributes) == 1
    assert span.attributes.get("ec") == 0

    attributes = {
        "field1": 1,
        "field2": "two",
    }
    span.mark_as_errored(attributes)

    assert span.attributes
    assert len(span.attributes) == 3
    assert span.attributes.get("ec") == 1
    assert "field1" in span.attributes.keys()
    assert span.attributes.get("field2") == "two"

    span.mark_as_errored()

    assert span.attributes
    assert len(span.attributes) == 3
    assert span.attributes.get("ec") == 2
    assert "field1" in span.attributes.keys()
    assert span.attributes.get("field2") == "two"


def test_span_mark_as_errored_exception(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    with patch(
        "instana.span.span.InstanaSpan.set_attribute",
        side_effect=Exception("mocked error"),
    ):
        span.mark_as_errored()
        assert not span.attributes


def test_span_assure_errored_default(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    span.assure_errored()

    assert span.attributes
    assert len(span.attributes) == 1
    assert span.attributes.get("ec") == 1


def test_span_assure_errored(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    attributes = {
        "ec": 0,
    }
    span = InstanaSpan(span_name, span_context, span_processor, attributes=attributes)

    assert span.attributes
    assert len(span.attributes) == 1
    assert span.attributes.get("ec") == 0

    span.assure_errored()

    assert span.attributes
    assert len(span.attributes) == 1
    assert span.attributes.get("ec") == 1


def test_span_assure_errored_exception(
    span_context: SpanContext, span_processor: StanRecorder
) -> None:
    span_name = "test-span"
    span = InstanaSpan(span_name, span_context, span_processor)

    with patch(
        "instana.span.span.InstanaSpan.set_attribute",
        side_effect=Exception("mocked error"),
    ):
        span.assure_errored()
        assert not span.attributes


def test_get_current_span(context) -> None:
    span = get_current_span(context)
    assert isinstance(span, InstanaSpan)


def test_get_current_span_INVALID_SPAN() -> None:
    span = get_current_span()

    assert span
    assert span == INVALID_SPAN
