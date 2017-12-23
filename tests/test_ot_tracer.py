import opentracing
import instana.tracer
from nose.tools import assert_equals


def test_tracer_basics():
    assert hasattr(instana.tracer, 'InstanaTracer')
    assert hasattr(opentracing.tracer, "start_span")
    assert hasattr(opentracing.tracer, "inject")
    assert hasattr(opentracing.tracer, "extract")
