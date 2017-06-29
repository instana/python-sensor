import opentracing
import instana.tracer
import string
from nose.tools import assert_equals


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
