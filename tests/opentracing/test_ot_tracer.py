import opentracing


def test_tracer_basics():
    assert hasattr(opentracing.tracer, "start_span")
    assert hasattr(opentracing.tracer, "inject")
    assert hasattr(opentracing.tracer, "extract")
