import opentracing
import instana.tracer
import string
from nose.tools import assert_equals


def test_span_basics():
    opentracing.global_tracer = instana.tracer.InstanaTracer()
    span = opentracing.global_tracer.start_span("blah")
    assert hasattr(span, "finish")
    assert hasattr(span, "set_tag")
    assert hasattr(span, "tags")
    assert hasattr(span, "operation_name")
    assert hasattr(span, "set_baggage_item")
    assert hasattr(span, "get_baggage_item")
    assert hasattr(span, "context")
    assert hasattr(span, "log")
