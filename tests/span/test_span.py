# (c) Copyright IBM Corp. 2024

import logging
import time
from typing import Generator
from unittest.mock import patch

import pytest
from opentelemetry.trace.status import Status, StatusCode

from instana.recorder import StanRecorder
from instana.span.span import INVALID_SPAN, Event, InstanaSpan, get_current_span
from instana.span_context import SpanContext


class TestSpan:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.span = None
        yield
        if isinstance(self.span, InstanaSpan):
            self.span.events.clear()

    def test_span_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        trace_id: int,
        span_id: int,
    ) -> None:
        span_name = "test-span"
        timestamp = time.time_ns()
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert self.span is not None
        assert isinstance(self.span, InstanaSpan)
        assert self.span.name == span_name

        context = self.span.context
        assert isinstance(context, SpanContext)
        assert context.trace_id == trace_id
        assert context.span_id == span_id

        assert self.span.start_time
        assert isinstance(self.span.start_time, int)
        assert self.span.start_time > timestamp
        assert not self.span.end_time
        assert not self.span.attributes
        assert not self.span.events
        assert self.span.is_recording()
        assert self.span.status
        assert self.span.status.is_unset

    def test_span_get_span_context(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        trace_id: int,
        span_id: int,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        context = self.span.get_span_context()
        assert isinstance(context, SpanContext)
        assert context.trace_id == trace_id
        assert context.span_id == span_id
        assert context == self.span.context

    def test_span_set_attributes_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert not self.span.attributes

        attributes = {
            "field1": 1,
            "field2": "two",
        }
        self.span.set_attributes(attributes)

        assert self.span.attributes
        assert len(self.span.attributes) == 2
        assert "field1" in self.span.attributes.keys()
        assert "two" == self.span.attributes.get("field2")

    def test_span_set_attributes(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        attributes = {
            "field1": 1,
            "field2": "two",
        }
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )

        assert self.span.attributes
        assert len(self.span.attributes) == 2
        assert "field1" in self.span.attributes.keys()
        assert "two" == self.span.attributes.get("field2")

        attributes = {
            "field3": True,
            "field4": ["four", "vier", "quatro"],
        }
        self.span.set_attributes(attributes)

        assert len(self.span.attributes) == 4
        assert "field3" in self.span.attributes.keys()
        assert "vier" in self.span.attributes.get("field4")

    def test_span_set_attribute_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert not self.span.attributes

        attributes = {
            "field1": 1,
            "field2": "two",
        }
        for key, value in attributes.items():
            self.span.set_attribute(key, value)

        assert self.span.attributes
        assert len(self.span.attributes) == 2
        assert "field1" in self.span.attributes.keys()
        assert "two" == self.span.attributes.get("field2")

    def test_span_set_attribute(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        attributes = {
            "field1": 1,
            "field2": "two",
        }
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )

        assert self.span.attributes
        assert len(self.span.attributes) == 2
        assert "field1" in self.span.attributes.keys()
        assert "two" == self.span.attributes.get("field2")

        attributes = {
            "field3": True,
            "field4": ["four", "vier", "quatro"],
        }
        for key, value in attributes.items():
            self.span.set_attribute(key, value)

        assert len(self.span.attributes) == 4
        assert "field3" in self.span.attributes.keys()
        assert "vier" in self.span.attributes.get("field4")

    def test_span_update_name(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span-1"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert self.span is not None
        assert isinstance(self.span, InstanaSpan)
        assert self.span.name == span_name

        new_span_name = "test-span-2"
        self.span.update_name(new_span_name)
        assert self.span is not None
        assert isinstance(self.span, InstanaSpan)
        assert self.span.name == new_span_name

    def test_span_set_status_with_Status_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="opentelemetry.trace.status")
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert self.span.status
        assert self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code == StatusCode.UNSET
        assert self.span.status.status_code != StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

        status_desc = "Status is OK."
        span_status = Status(status_code=StatusCode.OK, description=status_desc)

        assert (
            "description should only be set when status_code is set to StatusCode.ERROR"
            in caplog.messages
        )

        self.span.set_status(span_status)

        assert self.span.status
        assert not self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code == StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

    def test_span_set_status_with_Status_and_desc(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="opentelemetry.trace.status")
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert self.span.status
        assert self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code == StatusCode.UNSET
        assert self.span.status.status_code != StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

        status_desc = "Status is OK."
        span_status = Status(status_code=StatusCode.OK, description=status_desc)

        assert (
            "description should only be set when status_code is set to StatusCode.ERROR"
            in caplog.messages
        )

        set_status_desc = "Test"
        self.span.set_status(span_status, set_status_desc)
        excepted_log = f"Description {set_status_desc} ignored. Use either `Status` or `(StatusCode, Description)`"

        assert self.span.status
        assert not self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert excepted_log in caplog.messages
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code == StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

    def test_span_set_status_with_StatusUNSET_to_StatusERROR(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="opentelemetry.trace.status")
        span_name = "test-span"
        status_desc = "Status is UNSET."
        span_status = Status(status_code=StatusCode.UNSET, description=status_desc)

        assert (
            "description should only be set when status_code is set to StatusCode.ERROR"
            in caplog.messages
        )

        self.span = InstanaSpan(
            span_name, span_context, span_processor, status=span_status
        )

        assert self.span.status
        assert self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code == StatusCode.UNSET
        assert self.span.status.status_code != StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

        status_desc = "Houston we have a problem!"
        span_status = Status(StatusCode.ERROR, status_desc)
        self.span.set_status(span_status)

        assert self.span.status
        assert not self.span.status.is_unset
        assert not self.span.status.is_ok
        assert self.span.status.description == status_desc
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code != StatusCode.OK
        assert self.span.status.status_code == StatusCode.ERROR

    def test_span_set_status_with_StatusOK_to_StatusERROR(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="opentelemetry.trace.status")

        span_name = "test-span"
        status_desc = "Status is OK."
        span_status = Status(status_code=StatusCode.OK, description=status_desc)

        assert (
            "description should only be set when status_code is set to StatusCode.ERROR"
            in caplog.messages
        )

        self.span = InstanaSpan(
            span_name, span_context, span_processor, status=span_status
        )

        assert self.span.status
        assert not self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code == StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

        status_desc = "Houston we have a problem!"
        span_status = Status(StatusCode.ERROR, status_desc)
        self.span.set_status(span_status)

        assert self.span.status
        assert not self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code == StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

    def test_span_set_status_with_StatusCode_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert self.span.status
        assert self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code == StatusCode.UNSET
        assert self.span.status.status_code != StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

        span_status_code = StatusCode(StatusCode.OK)

        self.span.set_status(span_status_code)

        assert self.span.status
        assert not self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code == StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

    def test_span_set_status_with_StatusCode_and_desc(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="opentelemetry.trace.status")

        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert self.span.status
        assert self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code == StatusCode.UNSET
        assert self.span.status.status_code != StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

        status_desc = "Status is OK."
        span_status_code = StatusCode(StatusCode.OK)
        self.span.set_status(span_status_code, status_desc)

        assert self.span.status
        assert not self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code == StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR
        assert (
            "description should only be set when status_code is set to StatusCode.ERROR"
            in caplog.messages
        )

    def test_span_set_status_with_StatusCodeUNSET_to_StatusCodeERROR(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="opentelemetry.trace.status")

        span_name = "test-span"
        status_desc = "Status is UNSET."
        span_status = Status(status_code=StatusCode.UNSET, description=status_desc)

        assert (
            "description should only be set when status_code is set to StatusCode.ERROR"
            in caplog.messages
        )

        self.span = InstanaSpan(
            span_name, span_context, span_processor, status=span_status
        )

        assert self.span.status
        assert self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code == StatusCode.UNSET
        assert self.span.status.status_code != StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

        status_desc = "Houston we have a problem!"
        span_status_code = StatusCode(StatusCode.ERROR)
        self.span.set_status(span_status_code, status_desc)

        assert self.span.status
        assert not self.span.status.is_unset
        assert not self.span.status.is_ok
        assert self.span.status.description == status_desc
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code != StatusCode.OK
        assert self.span.status.status_code == StatusCode.ERROR

    def test_span_set_status_with_StatusCodeOK_to_StatusCodeERROR(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="opentelemetry.trace.status")

        span_name = "test-span"
        status_desc = "Status is OK."
        span_status = Status(status_code=StatusCode.OK, description=status_desc)

        assert (
            "description should only be set when status_code is set to StatusCode.ERROR"
            in caplog.messages
        )

        self.span = InstanaSpan(
            span_name, span_context, span_processor, status=span_status
        )

        assert self.span.status
        assert not self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code == StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

        status_desc = "Houston we have a problem!"
        span_status_code = StatusCode(StatusCode.ERROR)
        self.span.set_status(span_status_code, status_desc)

        assert self.span.status
        assert not self.span.status.is_unset
        assert self.span.status.is_ok
        assert not self.span.status.description
        assert self.span.status.status_code != StatusCode.UNSET
        assert self.span.status.status_code == StatusCode.OK
        assert self.span.status.status_code != StatusCode.ERROR

    def test_span_add_event_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert not self.span.events

        event_name = "event1"
        attributes = {
            "field1": 1,
            "field2": "two",
        }
        timestamp = time.time_ns()
        self.span.add_event(event_name, attributes, timestamp)

        assert self.span.events
        assert len(self.span.events) == 1
        for event in self.span.events:
            assert isinstance(event, Event)
            assert event.name == event_name
            assert event.timestamp == timestamp
            assert len(event.attributes) == 2

    def test_span_add_event(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        event_name1 = "event1"
        attributes = {
            "field1": 1,
            "field2": "two",
        }
        timestamp1 = time.time_ns()
        event = Event(event_name1, attributes, timestamp1)
        self.span = InstanaSpan(span_name, span_context, span_processor, events=[event])

        assert self.span.events
        assert len(self.span.events) == 1
        for event in self.span.events:
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
        self.span.add_event(event_name2, attributes, timestamp2)

        assert len(self.span.events) == 2
        for event in self.span.events:
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
            ("kafka", "kafka.error"),
        ],
    )
    def test_span_record_exception_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        span_name: str,
        span_attribute: str,
    ) -> None:
        exception_msg = "Test Exception"

        exception = Exception(exception_msg)
        self.span = InstanaSpan(span_name, span_context, span_processor)

        self.span.record_exception(exception)

        assert span_name == self.span.name
        assert 1 == self.span.attributes.get("ec", 0)
        if span_attribute:
            assert span_attribute in self.span.attributes.keys()
            assert exception_msg == self.span.attributes.get(span_attribute, None)
        else:
            event = self.span.events[-1]  # always get the latest event
            assert isinstance(event, Event)
            assert "exception" == event.name
            assert exception_msg == event.attributes.get("message", None)

    def test_span_record_exception_with_attribute(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        exception_msg = "Test Exception"
        attributes = {
            "custom_attr": 0,
        }

        exception = Exception(exception_msg)
        self.span = InstanaSpan(span_name, span_context, span_processor)

        self.span.record_exception(exception, attributes)

        assert span_name == self.span.name
        assert 1 == self.span.attributes.get("ec", 0)

        event = self.span.events[-1]  # always get the latest event
        assert isinstance(event, Event)
        assert 2 == len(event.attributes)
        assert exception_msg == event.attributes.get("message", None)
        assert 0 == event.attributes.get("custom_attr", None)

    def test_span_record_exception_with_Exception_msg(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "wsgi"
        span_attribute = "http.error"
        exception_msg = "Test Exception"

        exception = Exception()
        exception.message = exception_msg
        self.span = InstanaSpan(span_name, span_context, span_processor)

        self.span.record_exception(exception)

        assert span_name == self.span.name
        assert 1 == self.span.attributes.get("ec", 0)
        assert span_attribute in self.span.attributes.keys()
        assert exception_msg == self.span.attributes.get(span_attribute, None)

    def test_span_record_exception_with_Exception_none_msg(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "wsgi"
        span_attribute = "http.error"

        exception = Exception()
        exception.message = None
        self.span = InstanaSpan(span_name, span_context, span_processor)

        self.span.record_exception(exception)

        assert span_name == self.span.name
        assert 1 == self.span.attributes.get("ec", 0)
        assert span_attribute in self.span.attributes.keys()
        assert "Exception()" == self.span.attributes.get(span_attribute, None)

    def test_span_record_exception_with_Exception_raised(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"

        exception = None
        self.span = InstanaSpan(span_name, span_context, span_processor)

        with patch(
            "instana.span.span.InstanaSpan.add_event",
            side_effect=Exception("mocked error"),
        ):
            with pytest.raises(Exception):
                self.span.record_exception(exception)

    def test_span_end_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert not self.span.end_time

        self.span.end()

        assert self.span.end_time
        assert isinstance(self.span.end_time, int)

    def test_span_end(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"

        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert not self.span.end_time

        timestamp_end = time.time_ns()
        self.span.end(timestamp_end)

        assert self.span.end_time
        assert self.span.end_time == timestamp_end

    def test_span_mark_as_errored_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        attributes = {
            "ec": 0,
        }
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )

        assert self.span.attributes
        assert len(self.span.attributes) == 1
        assert self.span.attributes.get("ec") == 0

        self.span.mark_as_errored()

        assert self.span.attributes
        assert len(self.span.attributes) == 1
        assert self.span.attributes.get("ec") == 1

    def test_span_mark_as_errored(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        attributes = {
            "ec": 0,
        }
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )

        assert self.span.attributes
        assert len(self.span.attributes) == 1
        assert self.span.attributes.get("ec") == 0

        attributes = {
            "field1": 1,
            "field2": "two",
        }
        self.span.mark_as_errored(attributes)

        assert self.span.attributes
        assert len(self.span.attributes) == 3
        assert self.span.attributes.get("ec") == 1
        assert "field1" in self.span.attributes.keys()
        assert self.span.attributes.get("field2") == "two"

        self.span.mark_as_errored()

        assert self.span.attributes
        assert len(self.span.attributes) == 3
        assert self.span.attributes.get("ec") == 2
        assert "field1" in self.span.attributes.keys()
        assert self.span.attributes.get("field2") == "two"

    def test_span_mark_as_errored_exception(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        with patch(
            "instana.span.span.InstanaSpan.set_attribute",
            side_effect=Exception("mocked error"),
        ):
            self.span.mark_as_errored()
            assert not self.span.attributes

    def test_span_assure_errored_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        self.span.assure_errored()

        assert self.span.attributes
        assert len(self.span.attributes) == 1
        assert self.span.attributes.get("ec") == 1

    def test_span_assure_errored(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        attributes = {
            "ec": 0,
        }
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )

        assert self.span.attributes
        assert len(self.span.attributes) == 1
        assert self.span.attributes.get("ec") == 0

        self.span.assure_errored()

        assert self.span.attributes
        assert len(self.span.attributes) == 1
        assert self.span.attributes.get("ec") == 1

    def test_span_assure_errored_exception(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        with patch(
            "instana.span.span.InstanaSpan.set_attribute",
            side_effect=Exception("mocked error"),
        ):
            self.span.assure_errored()
            assert not self.span.attributes

    def test_get_current_span(self, context: SpanContext) -> None:
        self.span = get_current_span(context)
        assert isinstance(self.span, InstanaSpan)

    def test_get_current_span_INVALID_SPAN(self) -> None:
        self.span = get_current_span()

        assert self.span
        assert self.span == INVALID_SPAN

    def test_span_duration_default(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert not self.span.end_time
        assert not self.span.duration

        self.span.end()

        assert self.span.end_time
        assert self.span.duration
        assert isinstance(self.span.duration, int)
        assert self.span.duration > 0

    def test_span_duration(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-span"
        self.span = InstanaSpan(span_name, span_context, span_processor)

        assert not self.span.end_time
        assert not self.span.duration

        timestamp_end = time.time_ns()
        self.span.end(timestamp_end)

        assert self.span.end_time
        assert self.span.end_time == timestamp_end
        assert self.span.duration
        assert isinstance(self.span.duration, int)
        assert self.span.duration > 0
        assert self.span.duration == (timestamp_end - self.span.start_time)
