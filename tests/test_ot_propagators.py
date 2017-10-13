import instana.http_propagator as ihp
import opentracing as ot
from instana import tracer, options, util
from nose.tools import assert_equals
import inspect


def test_basics():
    inspect.isclass(ihp.HTTPPropagator)

    inject_func = getattr(ihp.HTTPPropagator, "inject", None)
    assert inject_func
    assert inspect.ismethod(inject_func)

    extract_func = getattr(ihp.HTTPPropagator, "extract", None)
    assert extract_func
    assert inspect.ismethod(extract_func)


def test_inject():
    opts = options.Options()
    ot.global_tracer = tracer.InstanaTracer(opts)

    carrier = {}
    span = ot.global_tracer.start_span("nosetests")
    ot.global_tracer.inject(span.context, ot.Format.HTTP_HEADERS, carrier)

    assert 'X-Instana-T' in carrier
    assert_equals(carrier['X-Instana-T'], util.id_to_header(span.context.trace_id))
    assert 'X-Instana-S' in carrier
    assert_equals(carrier['X-Instana-S'], util.id_to_header(span.context.span_id))
    assert 'X-Instana-L' in carrier
    assert_equals(carrier['X-Instana-L'], "1")
