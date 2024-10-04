# (c) Copyright IBM Corp. 2024

import time

from instana.span.readable_span import Event


def test_span_event_defaults():
    event_name = "test-span-event"
    event = Event(event_name)

    assert event
    assert isinstance(event, Event)
    assert event.name == event_name
    assert not event.attributes
    assert isinstance(event.timestamp, int)
    assert event.timestamp < time.time_ns()


def test_span_event():
    event_name = "test-span-event"
    attributes = {
        "field1": 1,
        "field2": "two",
    }
    timestamp = time.time_ns()

    event = Event(event_name, attributes, timestamp)

    assert event
    assert isinstance(event, Event)
    assert event.name == event_name
    assert event.attributes
    assert len(event.attributes) == 2
    assert "field1" in event.attributes.keys()
    assert "two" == event.attributes.get("field2")
    assert event.timestamp == timestamp


def test_event_with_params() -> None:
    name = "sample-event"
    attributes = ["attribute"]
    timestamp = time.time_ns()
    event = Event(name, attributes, timestamp)

    assert event.name == name
    assert event.attributes == attributes
    assert event.timestamp == timestamp
