import sys
import json
import time
import unittest
import opentracing
from uuid import UUID
from instana.util import to_json
from instana.singletons import tracer

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

class TestOTSpan(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        opentracing.tracer = tracer
        recorder = opentracing.tracer.recorder
        recorder.clear_spans()

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_span_interface(self):
        span = opentracing.tracer.start_span("blah")
        assert hasattr(span, "finish")
        assert hasattr(span, "set_tag")
        assert hasattr(span, "tags")
        assert hasattr(span, "operation_name")
        assert hasattr(span, "set_baggage_item")
        assert hasattr(span, "get_baggage_item")
        assert hasattr(span, "context")
        assert hasattr(span, "log")

    def test_span_ids(self):
        count = 0
        while count <= 1000:
            count += 1
            span = opentracing.tracer.start_span("test_span_ids")
            context = span.context
            assert 0 <= int(context.span_id, 16) <= 18446744073709551615
            assert 0 <= int(context.trace_id, 16) <= 18446744073709551615

    def test_span_fields(self):
        span = opentracing.tracer.start_span("mycustom")
        self.assertEqual("mycustom", span.operation_name)
        assert span.context

        span.set_tag("tagone", "string")
        span.set_tag("tagtwo", 150)

        self.assertEqual("string", span.tags['tagone'])
        self.assertEqual(150, span.tags['tagtwo'])

    def test_span_queueing(self):
        recorder = opentracing.tracer.recorder

        count = 1
        while count <= 20:
            count += 1
            span = opentracing.tracer.start_span("queuethisplz")
            span.set_tag("tagone", "string")
            span.set_tag("tagtwo", 150)
            span.finish()

        self.assertEqual(20, recorder.queue_size())

    def test_sdk_spans(self):
        recorder = opentracing.tracer.recorder

        span = opentracing.tracer.start_span("custom_sdk_span")
        span.set_tag("tagone", "string")
        span.set_tag("tagtwo", 150)
        span.set_tag('span.kind', "entry")
        time.sleep(0.5)
        span.finish()

        spans = recorder.queued_spans()
        assert 1, len(spans)

        sdk_span = spans[0]
        self.assertEqual('sdk', sdk_span.n)
        self.assertEqual(None, sdk_span.p)
        self.assertEqual(sdk_span.s, sdk_span.t)
        assert sdk_span.ts
        assert sdk_span.ts > 0
        assert sdk_span.d
        assert sdk_span.d > 0

        assert sdk_span.data
        assert sdk_span.data["sdk"]
        self.assertEqual('entry', sdk_span.data["sdk"]["type"])
        self.assertEqual('custom_sdk_span', sdk_span.data["sdk"]["name"])
        assert sdk_span.data["sdk"]["custom"]
        assert sdk_span.data["sdk"]["custom"]["tags"]

    def test_span_kind(self):
        recorder = opentracing.tracer.recorder

        span = opentracing.tracer.start_span("custom_sdk_span")
        span.set_tag('span.kind', "consumer")
        span.finish()

        span = opentracing.tracer.start_span("custom_sdk_span")
        span.set_tag('span.kind', "server")
        span.finish()

        span = opentracing.tracer.start_span("custom_sdk_span")
        span.set_tag('span.kind', "producer")
        span.finish()

        span = opentracing.tracer.start_span("custom_sdk_span")
        span.set_tag('span.kind', "client")
        span.finish()

        span = opentracing.tracer.start_span("custom_sdk_span")
        span.set_tag('span.kind', "blah")
        span.finish()

        spans = recorder.queued_spans()
        assert 5, len(spans)

        span = spans[0]
        self.assertEqual('entry', span.data["sdk"]["type"])

        span = spans[1]
        self.assertEqual('entry', span.data["sdk"]["type"])

        span = spans[2]
        self.assertEqual('exit', span.data["sdk"]["type"])

        span = spans[3]
        self.assertEqual('exit', span.data["sdk"]["type"])

        span = spans[4]
        self.assertEqual('intermediate', span.data["sdk"]["type"])

        span = spans[0]
        self.assertEqual(1, span.k)

        span = spans[1]
        self.assertEqual(1, span.k)

        span = spans[2]
        self.assertEqual(2, span.k)

        span = spans[3]
        self.assertEqual(2, span.k)

        span = spans[4]
        self.assertEqual(3, span.k)

    def test_tag_values(self):
        with tracer.start_active_span('test') as scope:
            # Set a UUID class as a tag
            # If unchecked, this causes a json.dumps error: "ValueError: Circular reference detected"
            scope.span.set_tag('uuid', UUID(bytes=b'\x12\x34\x56\x78'*4))
            # Arbitrarily setting an instance of some class
            scope.span.set_tag('tracer', tracer)
            scope.span.set_tag('none', None)
            scope.span.set_tag('mylist', [1, 2, 3])
            scope.span.set_tag('myset', {"one", "two", "three"})

        spans = tracer.recorder.queued_spans()
        assert len(spans) == 1

        test_span = spans[0]
        assert(test_span)
        assert(len(test_span.data['sdk']['custom']['tags']) == 5)
        assert(test_span.data['sdk']['custom']['tags']['uuid'] == "UUID('12345678-1234-5678-1234-567812345678')")
        assert(test_span.data['sdk']['custom']['tags']['tracer'])
        assert(test_span.data['sdk']['custom']['tags']['none'] == 'None')
        assert(test_span.data['sdk']['custom']['tags']['mylist'] == '[1, 2, 3]')
        if PY2:
            assert(test_span.data['sdk']['custom']['tags']['myset'] == "set(['three', 'two', 'one'])")
        else:
            assert(test_span.data['sdk']['custom']['tags']['myset'] == "{'two', 'one', 'three'}")

        # Convert to JSON
        json_data = to_json(test_span)
        assert(json_data)

        # And back
        span_dict = json.loads(json_data)
        assert(len(span_dict['data']['sdk']['custom']['tags']) == 5)
        assert(span_dict['data']['sdk']['custom']['tags']['uuid'] == "UUID('12345678-1234-5678-1234-567812345678')")
        assert(span_dict['data']['sdk']['custom']['tags']['tracer'])
        assert(span_dict['data']['sdk']['custom']['tags']['none'] == 'None')
        assert(span_dict['data']['sdk']['custom']['tags']['mylist'] == '[1, 2, 3]')
        if PY2:
            assert(span_dict['data']['sdk']['custom']['tags']['myset'] == "set(['three', 'two', 'one'])")
        else:
            assert(span_dict['data']['sdk']['custom']['tags']['myset'] == "{'three', 'two', 'one'}")

    def test_tag_names(self):
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

