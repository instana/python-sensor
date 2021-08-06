# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.propagators.base_propagator import BasePropagator
from instana.w3c_trace_context.traceparent import Traceparent
from instana.w3c_trace_context.tracestate import Tracestate
from mock import patch, MagicMock
import unittest


class TestBasePropagator(unittest.TestCase):
    def setUp(self):
        self.bp = BasePropagator()

    @patch.object(Traceparent, "get_traceparent_fields")
    @patch.object(Traceparent, "validate")
    def test_extract_carrier_dict(self, mock_validate, mock_get_traceparent_fields):
        carrier = {
            'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
            'tracestate': 'congo=t61rcWkgMzE',
            'X-INSTANA-T': '1234d0e0e4736234',
            'X-INSTANA-S': '1234567890abcdef',
            'X-INSTANA-L': '1, correlationType=web; correlationId=1234567890abcdef'
        }
        mock_validate.return_value = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        mock_get_traceparent_fields.return_value = ["4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7"]
        ctx = self.bp.extract(carrier)
        self.assertEqual(ctx.correlation_id, '1234567890abcdef')
        self.assertEqual(ctx.correlation_type, "web")
        self.assertIsNone(ctx.instana_ancestor)
        self.assertEqual(ctx.level, 1)
        self.assertEqual(ctx.long_trace_id, "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertEqual(ctx.span_id, "00f067aa0ba902b7")
        self.assertFalse(ctx.synthetic)
        self.assertEqual(ctx.trace_id, "a3ce929d0e0e4736")  # 16 last chars from traceparent trace_id
        self.assertTrue(ctx.trace_parent)
        self.assertEqual(ctx.traceparent, '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01')
        self.assertEqual(ctx.tracestate, 'congo=t61rcWkgMzE')

    @patch.object(Traceparent, "validate")
    def test_extract_carrier_dict_validate_Exception_None_returned(self, mock_validate):
        """
        In this test case the traceparent header fails the validation, so traceparent and tracestate are not gonna used
        Additionally because in the instana L header the correlation flags are present we need to start a new ctx and
        the present values of 'X-INSTANA-T', 'X-INSTANA-S' headers should no be used. This means the ctx should be None
        :param mock_validate:
        :return:
        """
        carrier = {
            'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
            'tracestate': 'congo=t61rcWkgMzE',
            'X-INSTANA-T': '1234d0e0e4736234',
            'X-INSTANA-S': '1234567890abcdef',
            'X-INSTANA-L': '1, correlationType=web; correlationId=1234567890abcdef'
        }
        mock_validate.return_value = None
        ctx = self.bp.extract(carrier)
        self.assertIsNone(ctx)