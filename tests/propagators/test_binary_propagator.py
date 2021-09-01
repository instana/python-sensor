# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.propagators.binary_propagator import BinaryPropagator
from instana.span_context import SpanContext
import unittest


class TestBinaryPropagator(unittest.TestCase):
    def setUp(self):
        self.bp = BinaryPropagator()

    def test_inject_carrier_dict(self):
        carrier = {}
        ctx = SpanContext(span_id="1234567890abcdef", trace_id="1234d0e0e4736234",
                                  level=1, baggage={}, sampled=True,
                                  synthetic=False)
        carrier = self.bp.inject(ctx, carrier)
        self.assertEqual(carrier[b'x-instana-t'], b"1234d0e0e4736234")

    def test_inject_carrier_dict_w3c_True(self):
        carrier = {}
        ctx = SpanContext(span_id="1234567890abcdef", trace_id="1234d0e0e4736234",
                                  level=1, baggage={}, sampled=True,
                                  synthetic=False)
        carrier = self.bp.inject(ctx, carrier, disable_w3c_trace_context=False)
        self.assertEqual(carrier[b'x-instana-t'], b"1234d0e0e4736234")
        self.assertEqual(carrier[b'traceparent'], b'00-00000000000000001234d0e0e4736234-1234567890abcdef-01')
        self.assertEqual(carrier[b'tracestate'], b'in=1234d0e0e4736234;1234567890abcdef')

    def test_inject_carrier_list(self):
        carrier = []
        ctx = SpanContext(span_id="1234567890abcdef", trace_id="1234d0e0e4736234",
                                  level=1, baggage={}, sampled=True,
                                  synthetic=False)
        carrier = self.bp.inject(ctx, carrier)
        self.assertEqual(carrier[0], (b'x-instana-t', b'1234d0e0e4736234'))

    def test_inject_carrier_list_w3c_True(self):
        carrier = []
        ctx = SpanContext(span_id="1234567890abcdef", trace_id="1234d0e0e4736234",
                                  level=1, baggage={}, sampled=True,
                                  synthetic=False)
        carrier = self.bp.inject(ctx, carrier, disable_w3c_trace_context=False)
        self.assertEqual(carrier[2], (b'x-instana-t', b'1234d0e0e4736234'))
        self.assertEqual(carrier[0], (b'traceparent', b'00-00000000000000001234d0e0e4736234-1234567890abcdef-01'))
        self.assertEqual(carrier[1], (b'tracestate', b'in=1234d0e0e4736234;1234567890abcdef'))

    def test_inject_carrier_tupple(self):
        carrier = ()
        ctx = SpanContext(span_id="1234567890abcdef", trace_id="1234d0e0e4736234",
                                  level=1, baggage={}, sampled=True,
                                  synthetic=False)
        carrier = self.bp.inject(ctx, carrier)
        self.assertEqual(carrier[0], (b'x-instana-t', b'1234d0e0e4736234'))

    def test_inject_carrier_tupple_w3c_True(self):
        carrier = ()
        ctx = SpanContext(span_id="1234567890abcdef", trace_id="1234d0e0e4736234",
                                  level=1, baggage={}, sampled=True,
                                  synthetic=False)
        carrier = self.bp.inject(ctx, carrier, disable_w3c_trace_context=False)
        self.assertEqual(carrier[2], (b'x-instana-t', b'1234d0e0e4736234'))
        self.assertEqual(carrier[0], (b'traceparent', b'00-00000000000000001234d0e0e4736234-1234567890abcdef-01'))
        self.assertEqual(carrier[1], (b'tracestate', b'in=1234d0e0e4736234;1234567890abcdef'))

    def test_inject_carrier_set_exception(self):
        carrier = set()
        ctx = SpanContext(span_id="1234567890abcdef", trace_id="1234d0e0e4736234",
                                  level=1, baggage={}, sampled=True,
                                  synthetic=False)
        carrier = self.bp.inject(ctx, carrier)
        self.assertIsNone(carrier)