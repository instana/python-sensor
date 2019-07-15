import inspect

import basictracer
import opentracing as ot
from nose.tools import assert_equals

import instana.http_propagator as ihp
import instana.text_propagator as itp
from instana import options, span_context
from instana.tracer import InstanaTracer


def test_http_basics():
    inspect.isclass(ihp.HTTPPropagator)

    inject_func = getattr(ihp.HTTPPropagator, "inject", None)
    assert inject_func
    assert callable(inject_func)

    extract_func = getattr(ihp.HTTPPropagator, "extract", None)
    assert extract_func
    assert callable(extract_func)


def test_http_inject_with_dict():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {}
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.HTTP_HEADERS, carrier)

    assert 'X-Instana-T' in carrier
    assert_equals(carrier['X-Instana-T'], span.context.trace_id)
    assert 'X-Instana-S' in carrier
    assert_equals(carrier['X-Instana-S'], span.context.span_id)
    assert 'X-Instana-L' in carrier
    assert_equals(carrier['X-Instana-L'], "1")


def test_http_inject_with_list():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = []
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.HTTP_HEADERS, carrier)

    assert ('X-Instana-T', span.context.trace_id) in carrier
    assert ('X-Instana-S', span.context.span_id) in carrier
    assert ('X-Instana-L', "1") in carrier


def test_http_basic_extract():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {'X-Instana-T': '1', 'X-Instana-S': '1', 'X-Instana-L': '1'}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert type(ctx) is span_context.InstanaSpanContext
    assert_equals('0000000000000001', ctx.trace_id)
    assert_equals('0000000000000001', ctx.span_id)


def test_http_mixed_case_extract():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {'x-insTana-T': '1', 'X-inSTANa-S': '1', 'X-INstana-l': '1'}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert type(ctx) is span_context.InstanaSpanContext
    assert_equals('0000000000000001', ctx.trace_id)
    assert_equals('0000000000000001', ctx.span_id)


def test_http_no_context_extract():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert ctx is None


def test_http_128bit_headers():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {'X-Instana-T': '0000000000000000b0789916ff8f319f',
               'X-Instana-S': '0000000000000000b0789916ff8f319f', 'X-Instana-L': '1'}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert type(ctx) is span_context.InstanaSpanContext
    assert_equals('b0789916ff8f319f', ctx.trace_id)
    assert_equals('b0789916ff8f319f', ctx.span_id)


def test_text_basics():
    inspect.isclass(itp.TextPropagator)

    inject_func = getattr(itp.TextPropagator, "inject", None)
    assert inject_func
    assert callable(inject_func)

    extract_func = getattr(itp.TextPropagator, "extract", None)
    assert extract_func
    assert callable(extract_func)


def test_text_inject_with_dict():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {}
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.TEXT_MAP, carrier)

    assert 'X-INSTANA-T' in carrier
    assert_equals(carrier['X-INSTANA-T'], span.context.trace_id)
    assert 'X-INSTANA-S' in carrier
    assert_equals(carrier['X-INSTANA-S'], span.context.span_id)
    assert 'X-INSTANA-L' in carrier
    assert_equals(carrier['X-INSTANA-L'], "1")


def test_text_inject_with_list():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = []
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.TEXT_MAP, carrier)

    assert ('X-INSTANA-T', span.context.trace_id) in carrier
    assert ('X-INSTANA-S', span.context.span_id) in carrier
    assert ('X-INSTANA-L', "1") in carrier


def test_text_basic_extract():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {'X-INSTANA-T': '1', 'X-INSTANA-S': '1', 'X-INSTANA-L': '1'}
    ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

    assert type(ctx) is span_context.InstanaSpanContext
    assert_equals('0000000000000001', ctx.trace_id)
    assert_equals('0000000000000001', ctx.span_id)


def test_text_mixed_case_extract():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {'x-insTana-T': '1', 'X-inSTANa-S': '1', 'X-INstana-l': '1'}
    ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

    assert(ctx is None)


def test_text_no_context_extract():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {}
    ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

    assert ctx is None


def test_text_128bit_headers():
    opts = options.Options()
    ot.tracer = InstanaTracer(opts)

    carrier = {'X-INSTANA-T': '0000000000000000b0789916ff8f319f',
               'X-INSTANA-S': ' 0000000000000000b0789916ff8f319f', 'X-INSTANA-L': '1'}
    ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

    assert type(ctx) is span_context.InstanaSpanContext
    assert_equals('b0789916ff8f319f', ctx.trace_id)
    assert_equals('b0789916ff8f319f', ctx.span_id)
