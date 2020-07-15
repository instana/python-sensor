from __future__ import absolute_import

from uuid import UUID
from instana.util import to_json
from instana.singletons import tracer


def setup_method():
    """ Clear all spans before a test run """
    tracer.recorder.clear_spans()


def test_to_json_bad_tag_values():
    with tracer.start_active_span('test') as scope:
        # Set a UUID class as a tag
        # If unchecked, this causes a json.dumps error: "ValueError: Circular reference detected"
        scope.span.set_tag('uuid', UUID(bytes=b'\x12\x34\x56\x78'*4))
        # Arbitrarily setting an instance of some class
        scope.span.set_tag('tracer', tracer)
        scope.span.set_tag('none', None)


    spans = tracer.recorder.queued_spans()
    assert len(spans) == 1

    test_span = spans[0]
    assert(test_span)
    assert(len(test_span.data['sdk']['custom']['tags']) == 3)
    assert(test_span.data['sdk']['custom']['tags']['uuid'] == '12345678-1234-5678-1234-567812345678')
    assert(test_span.data['sdk']['custom']['tags']['tracer'])
    assert(test_span.data['sdk']['custom']['tags']['none'] == 'None')

    json_data = to_json(test_span)
    assert(json_data)


def test_to_json_bad_key_values():
    with tracer.start_active_span('test') as scope:
        # Tag names (keys) must be strings
        scope.span.set_tag(1234567890, 'This should not get set')

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 1

    test_span = spans[0]
    assert(test_span)
    assert(len(test_span.data['sdk']['custom']['tags']) == 0)

    json_data = to_json(test_span)
    assert(json_data)

