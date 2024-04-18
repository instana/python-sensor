# (c) Copyright IBM Corp. 2024

import time
from instana.span import Event


def test_span_event_defaults():
    event_name = "test-span-event"
    event = Event(event_name)

    assert event
    assert isinstance(event, Event)
    assert event.name == event_name
    assert not event.attributes
    assert isinstance(event.timestamp, int)


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
