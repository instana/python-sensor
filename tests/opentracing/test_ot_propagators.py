# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import inspect
import unittest

import opentracing as ot

import instana.propagators.http_propagator as ihp
import instana.propagators.text_propagator as itp
import instana.propagators.binary_propagator as ibp
from instana.span_context import SpanContext
from instana.tracer import InstanaTracer


class TestOTSpan(unittest.TestCase):
    def test_http_basics(self):
        inspect.isclass(ihp.HTTPPropagator)

        inject_func = getattr(ihp.HTTPPropagator, "inject", None)
        self.assertTrue(inject_func)
        self.assertTrue(callable(inject_func))

        extract_func = getattr(ihp.HTTPPropagator, "extract", None)
        self.assertTrue(extract_func)
        self.assertTrue(callable(extract_func))


    def test_http_inject_with_dict(self):
        ot.tracer = InstanaTracer()

        carrier = {}
        span = ot.tracer.start_span("unittest")
        ot.tracer.inject(span.context, ot.Format.HTTP_HEADERS, carrier)

        self.assertIn('X-INSTANA-T', carrier)
        self.assertEqual(carrier['X-INSTANA-T'], span.context.trace_id)
        self.assertIn('X-INSTANA-S', carrier)
        self.assertEqual(carrier['X-INSTANA-S'], span.context.span_id)
        self.assertIn('X-INSTANA-L', carrier)
        self.assertEqual(carrier['X-INSTANA-L'], "1")


    def test_http_inject_with_list(self):
        ot.tracer = InstanaTracer()

        carrier = []
        span = ot.tracer.start_span("unittest")
        ot.tracer.inject(span.context, ot.Format.HTTP_HEADERS, carrier)

        self.assertIn(('X-INSTANA-T', span.context.trace_id), carrier)
        self.assertIn(('X-INSTANA-S', span.context.span_id), carrier)
        self.assertIn(('X-INSTANA-L', "1"), carrier)


    def test_http_basic_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {'X-INSTANA-T': '1', 'X-INSTANA-S': '1', 'X-INSTANA-L': '1', 'X-INSTANA-SYNTHETIC': '1'}
        ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, '0000000000000001')
        self.assertEqual(ctx.span_id, '0000000000000001')
        self.assertTrue(ctx.synthetic)


    def test_http_extract_with_byte_keys(self):
        ot.tracer = InstanaTracer()

        carrier = {b'X-INSTANA-T': '1', b'X-INSTANA-S': '1', b'X-INSTANA-L': '1', b'X-INSTANA-SYNTHETIC': '1'}
        ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, '0000000000000001')
        self.assertEqual(ctx.span_id, '0000000000000001')
        self.assertTrue(ctx.synthetic)


    def test_http_extract_from_list_of_tuples(self):
        ot.tracer = InstanaTracer()

        carrier = [(b'user-agent', b'python-requests/2.23.0'), (b'accept-encoding', b'gzip, deflate'),
                   (b'accept', b'*/*'), (b'connection', b'keep-alive'),
                   (b'x-instana-t', b'1'), (b'x-instana-s', b'1'), (b'x-instana-l', b'1'), (b'X-INSTANA-SYNTHETIC', '1')]
        ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, '0000000000000001')
        self.assertEqual(ctx.span_id, '0000000000000001')
        self.assertTrue(ctx.synthetic)


    def test_http_mixed_case_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {'x-insTana-T': '1', 'X-inSTANa-S': '1', 'X-INstana-l': '1'}
        ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, '0000000000000001')
        self.assertEqual(ctx.span_id, '0000000000000001')
        self.assertFalse(ctx.synthetic)


    def test_http_extract_synthetic_only(self):
        ot.tracer = InstanaTracer()

        carrier = {'X-INSTANA-SYNTHETIC': '1'}
        ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertIsNone(ctx.trace_id)
        self.assertIsNone(ctx.span_id)
        self.assertTrue(ctx.synthetic)


    def test_http_default_context_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {}
        ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertIsNone(ctx.trace_id)
        self.assertIsNone(ctx.span_id)
        self.assertFalse(ctx.synthetic)

    def test_http_128bit_headers(self):
        ot.tracer = InstanaTracer()

        carrier = {'X-INSTANA-T': '0000000000000000b0789916ff8f319f',
                   'X-INSTANA-S': '0000000000000000b0789916ff8f319f', 'X-INSTANA-L': '1'}
        ctx = ot.tracer.extract(ot.Format.HTTP_HEADERS, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, 'b0789916ff8f319f')
        self.assertEqual(ctx.span_id, 'b0789916ff8f319f')


    def test_text_basics(self):
        inspect.isclass(itp.TextPropagator)

        inject_func = getattr(itp.TextPropagator, "inject", None)
        self.assertTrue(inject_func)
        self.assertTrue(callable(inject_func))

        extract_func = getattr(itp.TextPropagator, "extract", None)
        self.assertTrue(extract_func)
        self.assertTrue(callable(extract_func))


    def test_text_inject_with_dict(self):
        ot.tracer = InstanaTracer()

        carrier = {}
        span = ot.tracer.start_span("unittest")
        ot.tracer.inject(span.context, ot.Format.TEXT_MAP, carrier)

        self.assertIn('x-instana-t', carrier)
        self.assertEqual(carrier['x-instana-t'], span.context.trace_id)
        self.assertIn('x-instana-s', carrier)
        self.assertEqual(carrier['x-instana-s'], span.context.span_id)
        self.assertIn('x-instana-l', carrier)
        self.assertEqual(carrier['x-instana-l'], "1")


    def test_text_inject_with_list(self):
        ot.tracer = InstanaTracer()

        carrier = []
        span = ot.tracer.start_span("unittest")
        ot.tracer.inject(span.context, ot.Format.TEXT_MAP, carrier)

        self.assertIn(('x-instana-t', span.context.trace_id), carrier)
        self.assertIn(('x-instana-s', span.context.span_id), carrier)
        self.assertIn(('x-instana-l', "1"), carrier)


    def test_text_basic_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {'x-instana-t': '1', 'x-instana-s': '1', 'x-instana-l': '1'}
        ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, '0000000000000001')
        self.assertEqual(ctx.span_id, '0000000000000001')


    def test_text_mixed_case_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {'x-insTana-T': '1', 'X-inSTANa-S': '1', 'X-INstana-l': '1'}
        ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, '0000000000000001')
        self.assertEqual(ctx.span_id, '0000000000000001')


    def test_text_default_context_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {}
        ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertIsNone(ctx.trace_id)
        self.assertIsNone(ctx.span_id)
        self.assertFalse(ctx.synthetic)


    def test_text_128bit_headers(self):
        ot.tracer = InstanaTracer()

        carrier = {'x-instana-t': '0000000000000000b0789916ff8f319f',
                   'x-instana-s': ' 0000000000000000b0789916ff8f319f', 'X-INSTANA-L': '1'}
        ctx = ot.tracer.extract(ot.Format.TEXT_MAP, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, 'b0789916ff8f319f')
        self.assertEqual(ctx.span_id, 'b0789916ff8f319f')

    def test_binary_basics(self):
        inspect.isclass(ibp.BinaryPropagator)

        inject_func = getattr(ibp.BinaryPropagator, "inject", None)
        self.assertTrue(inject_func)
        self.assertTrue(callable(inject_func))

        extract_func = getattr(ibp.BinaryPropagator, "extract", None)
        self.assertTrue(extract_func)
        self.assertTrue(callable(extract_func))


    def test_binary_inject_with_dict(self):
        ot.tracer = InstanaTracer()

        carrier = {}
        span = ot.tracer.start_span("unittest")
        ot.tracer.inject(span.context, ot.Format.BINARY, carrier)

        self.assertIn(b'x-instana-t', carrier)
        self.assertEqual(carrier[b'x-instana-t'], str.encode(span.context.trace_id))
        self.assertIn(b'x-instana-s', carrier)
        self.assertEqual(carrier[b'x-instana-s'], str.encode(span.context.span_id))
        self.assertIn(b'x-instana-l', carrier)
        self.assertEqual(carrier[b'x-instana-l'], b'1')


    def test_binary_inject_with_list(self):
        ot.tracer = InstanaTracer()

        carrier = []
        span = ot.tracer.start_span("unittest")
        ot.tracer.inject(span.context, ot.Format.BINARY, carrier)

        self.assertIn((b'x-instana-t', str.encode(span.context.trace_id)), carrier)
        self.assertIn((b'x-instana-s', str.encode(span.context.span_id)), carrier)
        self.assertIn((b'x-instana-l', b'1'), carrier)


    def test_binary_basic_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {b'X-INSTANA-T': b'1', b'X-INSTANA-S': b'1', b'X-INSTANA-L': b'1', b'X-INSTANA-SYNTHETIC': b'1'}
        ctx = ot.tracer.extract(ot.Format.BINARY, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, '0000000000000001')
        self.assertEqual(ctx.span_id, '0000000000000001')
        self.assertTrue(ctx.synthetic)


    def test_binary_mixed_case_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {'x-insTana-T': '1', 'X-inSTANa-S': '1', 'X-INstana-l': '1', b'X-inStaNa-SYNtheTIC': b'1'}
        ctx = ot.tracer.extract(ot.Format.BINARY, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, '0000000000000001')
        self.assertEqual(ctx.span_id, '0000000000000001')
        self.assertTrue(ctx.synthetic)


    def test_binary_default_context_extract(self):
        ot.tracer = InstanaTracer()

        carrier = {}
        ctx = ot.tracer.extract(ot.Format.BINARY, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertIsNone(ctx.trace_id)
        self.assertIsNone(ctx.span_id)
        self.assertFalse(ctx.synthetic)


    def test_binary_128bit_headers(self):
        ot.tracer = InstanaTracer()

        carrier = {'X-INSTANA-T': '0000000000000000b0789916ff8f319f',
                   'X-INSTANA-S': ' 0000000000000000b0789916ff8f319f', 'X-INSTANA-L': '1'}
        ctx = ot.tracer.extract(ot.Format.BINARY, carrier)

        self.assertIsInstance(ctx, SpanContext)
        self.assertEqual(ctx.trace_id, 'b0789916ff8f319f')
        self.assertEqual(ctx.span_id, 'b0789916ff8f319f')
