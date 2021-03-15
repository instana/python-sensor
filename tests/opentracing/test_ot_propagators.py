# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import inspect

import opentracing as ot

import instana.propagators.http_propagator as ihp
import instana.propagators.text_propagator as itp
import instana.propagators.binary_propagator as ibp
from instana.span_context import SpanContext
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
    ot.tracer = InstanaTracer()

    carrier = {}
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.HTTP_HEADERS, carrier)

    assert 'X-INSTANA-T' in carrier
    assert carrier['X-INSTANA-T'] == span.context.trace_id
    assert 'X-INSTANA-S' in carrier
    assert carrier['X-INSTANA-S'] == span.context.span_id
    assert 'X-INSTANA-L' in carrier
    assert carrier['X-INSTANA-L'] == "1"


def test_http_inject_with_list():
    ot.tracer = InstanaTracer()

    carrier = []
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.HTTP_HEADERS, carrier)

    assert ('X-INSTANA-T', span.context.trace_id) in carrier
    assert ('X-INSTANA-S', span.context.span_id) in carrier
    assert ('X-INSTANA-L', "1") in carrier


def test_http_basic_extract():
    ot.tracer = InstanaTracer()

    carrier = {'X-INSTANA-T': '1', 'X-INSTANA-S': '1', 'X-INSTANA-L': '1', 'X-INSTANA-SYNTHETIC': '1'}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == '0000000000000001'
    assert ctx.span_id == '0000000000000001'
    assert ctx.synthetic


def test_http_extract_with_byte_keys():
    ot.tracer = InstanaTracer()

    carrier = {b'X-INSTANA-T': '1', b'X-INSTANA-S': '1', b'X-INSTANA-L': '1', b'X-INSTANA-SYNTHETIC': '1'}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == '0000000000000001'
    assert ctx.span_id == '0000000000000001'
    assert ctx.synthetic


def test_http_extract_from_list_of_tuples():
    ot.tracer = InstanaTracer()

    carrier = [(b'user-agent', b'python-requests/2.23.0'), (b'accept-encoding', b'gzip, deflate'),
               (b'accept', b'*/*'), (b'connection', b'keep-alive'),
               (b'x-instana-t', b'1'), (b'x-instana-s', b'1'), (b'x-instana-l', b'1'), (b'X-INSTANA-SYNTHETIC', '1')]
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == '0000000000000001'
    assert ctx.span_id == '0000000000000001'
    assert ctx.synthetic


def test_http_mixed_case_extract():
    ot.tracer = InstanaTracer()

    carrier = {'x-insTana-T': '1', 'X-inSTANa-S': '1', 'X-INstana-l': '1'}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == '0000000000000001'
    assert ctx.span_id == '0000000000000001'
    assert not ctx.synthetic


def test_http_extract_synthetic_only():
    ot.tracer = InstanaTracer()

    carrier = {'X-INSTANA-SYNTHETIC': '1'}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id is None
    assert ctx.span_id is None
    assert ctx.synthetic


def test_http_no_context_extract():
    ot.tracer = InstanaTracer()

    carrier = {}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert ctx is None


def test_http_128bit_headers():
    ot.tracer = InstanaTracer()

    carrier = {'X-INSTANA-T': '0000000000000000b0789916ff8f319f',
               'X-INSTANA-S': '0000000000000000b0789916ff8f319f', 'X-INSTANA-L': '1'}
    ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == 'b0789916ff8f319f'
    assert ctx.span_id == 'b0789916ff8f319f'


def test_text_basics():
    inspect.isclass(itp.TextPropagator)

    inject_func = getattr(itp.TextPropagator, "inject", None)
    assert inject_func
    assert callable(inject_func)

    extract_func = getattr(itp.TextPropagator, "extract", None)
    assert extract_func
    assert callable(extract_func)


def test_text_inject_with_dict():
    ot.tracer = InstanaTracer()

    carrier = {}
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.TEXT_MAP, carrier)

    assert 'x-instana-t' in carrier
    assert carrier['x-instana-t'] == span.context.trace_id
    assert 'x-instana-s' in carrier
    assert carrier['x-instana-s'] == span.context.span_id
    assert 'x-instana-l' in carrier
    assert carrier['x-instana-l'] == "1"


def test_text_inject_with_list():
    ot.tracer = InstanaTracer()

    carrier = []
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.TEXT_MAP, carrier)

    assert ('x-instana-t', span.context.trace_id) in carrier
    assert ('x-instana-s', span.context.span_id) in carrier
    assert ('x-instana-l', "1") in carrier


def test_text_basic_extract():
    ot.tracer = InstanaTracer()

    carrier = {'x-instana-t': '1', 'x-instana-s': '1', 'x-instana-l': '1'}
    ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == '0000000000000001'
    assert ctx.span_id == '0000000000000001'


def test_text_mixed_case_extract():
    ot.tracer = InstanaTracer()

    carrier = {'x-insTana-T': '1', 'X-inSTANa-S': '1', 'X-INstana-l': '1'}
    ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == '0000000000000001'
    assert ctx.span_id == '0000000000000001'


def test_text_no_context_extract():
    ot.tracer = InstanaTracer()

    carrier = {}
    ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

    assert ctx is None


def test_text_128bit_headers():
    ot.tracer = InstanaTracer()

    carrier = {'x-instana-t': '0000000000000000b0789916ff8f319f',
               'x-instana-s': ' 0000000000000000b0789916ff8f319f', 'X-INSTANA-L': '1'}
    ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

    assert isinstance(ctx, SpanContext)
    assert('b0789916ff8f319f' == ctx.span_id)
    assert ctx.trace_id == 'b0789916ff8f319f'
    assert ctx.span_id == 'b0789916ff8f319f'

def test_binary_basics():
    inspect.isclass(ibp.BinaryPropagator)

    inject_func = getattr(ibp.BinaryPropagator, "inject", None)
    assert inject_func
    assert callable(inject_func)

    extract_func = getattr(ibp.BinaryPropagator, "extract", None)
    assert extract_func
    assert callable(extract_func)


def test_binary_inject_with_dict():
    ot.tracer = InstanaTracer()

    carrier = {}
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.BINARY, carrier)

    assert b'x-instana-t' in carrier
    assert carrier[b'x-instana-t'] == str.encode(span.context.trace_id)
    assert b'x-instana-s' in carrier
    assert carrier[b'x-instana-s'] == str.encode(span.context.span_id)
    assert b'x-instana-l' in carrier
    assert carrier[b'x-instana-l'] == b'1'


def test_binary_inject_with_list():
    ot.tracer = InstanaTracer()

    carrier = []
    span = ot.tracer.start_span("nosetests")
    ot.tracer.inject(span.context, ot.Format.BINARY, carrier)

    assert (b'x-instana-t', str.encode(span.context.trace_id)) in carrier
    assert (b'x-instana-s', str.encode(span.context.span_id)) in carrier
    assert (b'x-instana-l', b'1') in carrier


def test_binary_basic_extract():
    ot.tracer = InstanaTracer()

    carrier = {b'X-INSTANA-T': b'1', b'X-INSTANA-S': b'1', b'X-INSTANA-L': b'1', b'X-INSTANA-SYNTHETIC': b'1'}
    ctx = ot.tracer.extract(ot.Format.BINARY, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == '0000000000000001'
    assert ctx.span_id == '0000000000000001'
    assert ctx.synthetic


def test_binary_mixed_case_extract():
    ot.tracer = InstanaTracer()

    carrier = {'x-insTana-T': '1', 'X-inSTANa-S': '1', 'X-INstana-l': '1', b'X-inStaNa-SYNtheTIC': b'1'}
    ctx = ot.tracer.extract(ot.Format.BINARY, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == '0000000000000001'
    assert ctx.span_id == '0000000000000001'
    assert ctx.synthetic


def test_binary_no_context_extract():
    ot.tracer = InstanaTracer()

    carrier = {}
    ctx = ot.tracer.extract(ot.Format.BINARY, carrier)

    assert ctx is None


def test_binary_128bit_headers():
    ot.tracer = InstanaTracer()

    carrier = {'X-INSTANA-T': '0000000000000000b0789916ff8f319f',
               'X-INSTANA-S': ' 0000000000000000b0789916ff8f319f', 'X-INSTANA-L': '1'}
    ctx = ot.tracer.extract(ot.Format.BINARY, carrier)

    assert isinstance(ctx, SpanContext)
    assert ctx.trace_id == 'b0789916ff8f319f'
    assert ctx.span_id == 'b0789916ff8f319f'
