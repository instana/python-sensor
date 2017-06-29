import opentracing
from nose.tools import assert_equals
import time

class OTSpanTest:
    def setUp():
        """ Clear all spans before a test run """
        recorder = opentracing.global_tracer.recorder
        recorder.clear_spans()

    def tearDown():
        """ Do nothing for now """
        return None


    def test_span_interface():
        span = opentracing.global_tracer.start_span("blah")
        assert hasattr(span, "finish")
        assert hasattr(span, "set_tag")
        assert hasattr(span, "tags")
        assert hasattr(span, "operation_name")
        assert hasattr(span, "set_baggage_item")
        assert hasattr(span, "get_baggage_item")
        assert hasattr(span, "context")
        assert hasattr(span, "log")


    def test_span_ids():
        count = 0
        while count <= 1000:
            count += 1
            span = opentracing.global_tracer.start_span("test_span_ids")
            context = span.context
            assert -9223372036854775808 <= context.span_id <= 9223372036854775807
            assert -9223372036854775808 <= context.trace_id <= 9223372036854775807


    def test_span_fields():
        span = opentracing.global_tracer.start_span("mycustom")
        assert_equals("mycustom", span.operation_name)
        assert span.context

        span.set_tag("tagone", "string")
        span.set_tag("tagtwo", 150)

        assert_equals("string", span.tags['tagone'])
        assert_equals(150, span.tags['tagtwo'])

    def test_span_queueing():
        recorder = opentracing.global_tracer.recorder

        count = 1
        while count <= 20:
            count += 1
            span = opentracing.global_tracer.start_span("queuethisplz")
            span.set_tag("tagone", "string")
            span.set_tag("tagtwo", 150)
            span.finish()

        assert_equals(20, recorder.queue_size())


    def test_sdk_spans():
        recorder = opentracing.global_tracer.recorder

        span = opentracing.global_tracer.start_span("custom_sdk_span")
        span.set_tag("tagone", "string")
        span.set_tag("tagtwo", 150)
        span.set_tag('span.kind', "entry")
        time.sleep(0.5)
        span.finish()

        spans = recorder.queued_spans()
        assert 1, len(spans)

        sdk_span = spans[0]
        assert_equals('sdk', sdk_span.n)
        assert_equals(None, sdk_span.p)
        assert_equals(sdk_span.s, sdk_span.t)
        assert sdk_span.ts
        assert sdk_span.ts > 0
        assert sdk_span.d
        assert sdk_span.d > 0
        assert_equals("py", sdk_span.ta)

        assert sdk_span.data
        assert sdk_span.data.sdk
        assert_equals('entry', sdk_span.data.sdk.Type)
        assert sdk_span.data.sdk.Custom
        assert sdk_span.data.sdk.Custom.tags
