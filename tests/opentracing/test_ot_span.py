# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import re
import sys
import json
import time
import unittest
from uuid import UUID

import opentracing

from instana.util import to_json
from instana.singletons import agent, tracer
from ..helpers import get_first_span_by_filter


class TestOTSpan(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        agent.options.service_name = None
        opentracing.tracer = tracer
        recorder = opentracing.tracer.recorder
        recorder.clear_spans()

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_span_interface(self):
        span = opentracing.tracer.start_span("blah")
        self.assertTrue(hasattr(span, "finish"))
        self.assertTrue(hasattr(span, "set_tag"))
        self.assertTrue(hasattr(span, "tags"))
        self.assertTrue(hasattr(span, "operation_name"))
        self.assertTrue(hasattr(span, "set_baggage_item"))
        self.assertTrue(hasattr(span, "get_baggage_item"))
        self.assertTrue(hasattr(span, "context"))
        self.assertTrue(hasattr(span, "log"))

    def test_span_ids(self):
        count = 0
        while count <= 1000:
            count += 1
            span = opentracing.tracer.start_span("test_span_ids")
            context = span.context
            self.assertTrue(0 <= int(context.span_id, 16) <= 18446744073709551615)
            self.assertTrue(0 <= int(context.trace_id, 16) <= 18446744073709551615)

    # Python 3.11 support is incomplete yet
    # TODO: Remove this once we find a workaround or DROP opentracing!
    @unittest.skipIf(sys.version_info >= (3, 11), reason="Raises not Implemented exception in OSX")
    def test_stacks(self):
        # Entry spans have no stack attached by default
        wsgi_span = opentracing.tracer.start_span("wsgi")
        self.assertIsNone(wsgi_span.stack)

        # SDK spans have no stack attached by default
        sdk_span = opentracing.tracer.start_span("unregistered_span_type")
        self.assertIsNone(sdk_span.stack)

        # Exit spans are no longer than 30 frames
        exit_span = opentracing.tracer.start_span("urllib3")
        self.assertLessEqual(len(exit_span.stack), 30)

    def test_span_fields(self):
        span = opentracing.tracer.start_span("mycustom")
        self.assertEqual("mycustom", span.operation_name)
        self.assertTrue(span.context)

        span.set_tag("tagone", "string")
        span.set_tag("tagtwo", 150)

        self.assertEqual("string", span.tags['tagone'])
        self.assertEqual(150, span.tags['tagtwo'])

    @unittest.skipIf(sys.platform == "darwin", reason="Raises not Implemented exception in OSX")
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
        self.assertEqual(1, len(spans))

        sdk_span = spans[0]
        self.assertEqual('sdk', sdk_span.n)
        self.assertEqual(None, sdk_span.p)
        self.assertEqual(sdk_span.s, sdk_span.t)
        self.assertTrue(sdk_span.ts)
        self.assertGreater(sdk_span.ts, 0)
        self.assertTrue(sdk_span.d)
        self.assertGreater(sdk_span.d, 0)

        self.assertTrue(sdk_span.data)
        self.assertTrue(sdk_span.data["sdk"])
        self.assertEqual('entry', sdk_span.data["sdk"]["type"])
        self.assertEqual('custom_sdk_span', sdk_span.data["sdk"]["name"])
        self.assertTrue(sdk_span.data["sdk"]["custom"])
        self.assertTrue(sdk_span.data["sdk"]["custom"]["tags"])

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
        self.assertEqual(5, len(spans))

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
            scope.span.set_tag('myset', {"one", 2})

        spans = tracer.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        test_span = spans[0]
        self.assertTrue(test_span)
        self.assertEqual(len(test_span.data['sdk']['custom']['tags']), 5)
        self.assertEqual(test_span.data['sdk']['custom']['tags']['uuid'], "UUID('12345678-1234-5678-1234-567812345678')")
        self.assertTrue(test_span.data['sdk']['custom']['tags']['tracer'])
        self.assertEqual(test_span.data['sdk']['custom']['tags']['none'], 'None')
        self.assertListEqual(test_span.data['sdk']['custom']['tags']['mylist'], [1, 2, 3])
        self.assertRegex(test_span.data['sdk']['custom']['tags']['myset'], r"\{.*,.*\}")

        # Convert to JSON
        json_data = to_json(test_span)
        self.assertTrue(json_data)

        # And back
        span_dict = json.loads(json_data)
        self.assertEqual(len(span_dict['data']['sdk']['custom']['tags']), 5)
        self.assertEqual(span_dict['data']['sdk']['custom']['tags']['uuid'], "UUID('12345678-1234-5678-1234-567812345678')")
        self.assertTrue(span_dict['data']['sdk']['custom']['tags']['tracer'])
        self.assertEqual(span_dict['data']['sdk']['custom']['tags']['none'], 'None')
        self.assertListEqual(span_dict['data']['sdk']['custom']['tags']['mylist'], [1, 2, 3])
        self.assertRegex(test_span.data['sdk']['custom']['tags']['myset'], r"{.*,.*}")

    def test_tag_names(self):
        with tracer.start_active_span('test') as scope:
            # Tag names (keys) must be strings
            scope.span.set_tag(1234567890, 'This should not get set')
            # Unicode key name
            scope.span.set_tag(u'asdf', 'This should be ok')

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 1)

        test_span = spans[0]
        self.assertTrue(test_span)
        self.assertEqual(len(test_span.data['sdk']['custom']['tags']), 1)
        self.assertEqual(test_span.data['sdk']['custom']['tags']['asdf'], 'This should be ok')

        json_data = to_json(test_span)
        self.assertTrue(json_data)

    def test_custom_service_name(self):
        # Set a custom service name
        agent.options.service_name = "custom_service_name"

        with tracer.start_active_span('entry_span') as scope:
            scope.span.set_tag('span.kind', 'server')
            scope.span.set_tag(u'type', 'entry_span')

            with tracer.start_active_span('intermediate_span', child_of=scope.span) as exit_scope:
                exit_scope.span.set_tag(u'type', 'intermediate_span')

            with tracer.start_active_span('exit_span', child_of=scope.span) as exit_scope:
                exit_scope.span.set_tag('span.kind', 'client')
                exit_scope.span.set_tag(u'type', 'exit_span')

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == "entry_span"
        entry_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(entry_span)

        filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == "intermediate_span"
        intermediate_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(intermediate_span)

        filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == "exit_span"
        exit_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(exit_span)

        self.assertTrue(entry_span)
        self.assertEqual(len(entry_span.data['sdk']['custom']['tags']), 2)
        self.assertEqual(entry_span.data['sdk']['custom']['tags']['type'], 'entry_span')
        self.assertEqual(entry_span.data['service'], 'custom_service_name')
        self.assertEqual(entry_span.k, 1)

        self.assertTrue(intermediate_span)
        self.assertEqual(len(intermediate_span.data['sdk']['custom']['tags']), 1)
        self.assertEqual(intermediate_span.data['sdk']['custom']['tags']['type'], 'intermediate_span')
        self.assertEqual(intermediate_span.data['service'], 'custom_service_name')
        self.assertEqual(intermediate_span.k, 3)

        self.assertTrue(exit_span)
        self.assertEqual(len(exit_span.data['sdk']['custom']['tags']), 2)
        self.assertEqual(exit_span.data['sdk']['custom']['tags']['type'], 'exit_span')
        self.assertEqual(exit_span.data['service'], 'custom_service_name')
        self.assertEqual(exit_span.k, 2)

    def test_span_log(self):
        with tracer.start_active_span('mylogspan') as scope:
            scope.span.log_kv({'Don McLean': 'American Pie'})
            scope.span.log_kv({'Elton John': 'Your Song'})

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 1)

        my_log_span = spans[0]
        self.assertEqual(my_log_span.n, 'sdk')

        log_data = my_log_span.data['sdk']['custom']['logs']
        self.assertEqual(len(log_data), 2)
