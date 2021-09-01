# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.propagators.http_propagator import HTTPPropagator
from instana.w3c_trace_context.traceparent import Traceparent
from instana.span_context import SpanContext
from mock import patch
import unittest


class TestHTTPPropagatorTC(unittest.TestCase):
    def setUp(self):
        self.hptc = HTTPPropagator()

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
        mock_get_traceparent_fields.return_value = ["00", "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7", "01"]
        ctx = self.hptc.extract(carrier)
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

    @patch.object(Traceparent, "get_traceparent_fields")
    @patch.object(Traceparent, "validate")
    def test_extract_carrier_list(self, mock_validate, mock_get_traceparent_fields):
        carrier = [('user-agent', 'python-requests/2.23.0'), ('accept-encoding', 'gzip, deflate'),
                   ('accept', '*/*'), ('connection', 'keep-alive'),
                   ('traceparent', '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'),
                   ('tracestate', 'congo=t61rcWkgMzE'),
                   ('X-INSTANA-T', '1234d0e0e4736234'),
                   ('X-INSTANA-S', '1234567890abcdef'),
                   ('X-INSTANA-L', '1')]

        mock_validate.return_value = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        mock_get_traceparent_fields.return_value = ["00", "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7", "01"]
        ctx = self.hptc.extract(carrier)
        self.assertIsNone(ctx.correlation_id)
        self.assertIsNone(ctx.correlation_type)
        self.assertIsNone(ctx.instana_ancestor)
        self.assertEqual(ctx.level, 1)
        self.assertIsNone(ctx.long_trace_id)
        self.assertEqual(ctx.span_id, "1234567890abcdef")
        self.assertFalse(ctx.synthetic)
        self.assertEqual(ctx.trace_id, "1234d0e0e4736234")  # 16 last chars from traceparent trace_id
        self.assertIsNone(ctx.trace_parent)
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
        ctx = self.hptc.extract(carrier)
        self.assertTrue(isinstance(ctx, SpanContext))
        assert ctx.trace_id is None
        assert ctx.span_id is None
        assert ctx.synthetic is False
        self.assertEqual(ctx.correlation_id, "1234567890abcdef")
        self.assertEqual(ctx.correlation_type, "web")

    @patch.object(Traceparent, "validate")
    def test_extract_fake_exception(self, mock_validate):
        carrier = {
            'traceparent': '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
            'tracestate': 'congo=t61rcWkgMzE',
            'X-INSTANA-T': '1234d0e0e4736234',
            'X-INSTANA-S': '1234567890abcdef',
            'X-INSTANA-L': '1, correlationType=web; correlationId=1234567890abcdef'
        }
        mock_validate.side_effect = Exception
        ctx = self.hptc.extract(carrier)
        self.assertIsNone(ctx)

    @patch.object(Traceparent, "get_traceparent_fields")
    @patch.object(Traceparent, "validate")
    def test_extract_carrier_dict_corrupted_level_header(self, mock_validate, mock_get_traceparent_fields):
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
            'X-INSTANA-L': '1, correlationTypeweb; correlationId1234567890abcdef'
        }
        mock_validate.return_value = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        mock_get_traceparent_fields.return_value = ["00", "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7", "01"]
        ctx = self.hptc.extract(carrier)
        self.assertIsNone(ctx.correlation_id)
        self.assertIsNone(ctx.correlation_type)
        self.assertIsNone(ctx.instana_ancestor)
        self.assertEqual(ctx.level, 1)
        self.assertEqual(ctx.long_trace_id, '4bf92f3577b34da6a3ce929d0e0e4736')
        self.assertEqual(ctx.span_id, "00f067aa0ba902b7")
        self.assertFalse(ctx.synthetic)
        self.assertEqual(ctx.trace_id, "a3ce929d0e0e4736")  # 16 last chars from traceparent trace_id
        self.assertTrue(ctx.trace_parent)
        self.assertEqual(ctx.traceparent, '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01')
        self.assertEqual(ctx.tracestate, 'congo=t61rcWkgMzE')

    @patch.object(Traceparent, "get_traceparent_fields")
    @patch.object(Traceparent, "validate")
    def test_extract_carrier_dict_level_header_not_splitable(self, mock_validate, mock_get_traceparent_fields):
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
            'X-INSTANA-L': ['1']
        }
        mock_validate.return_value = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        mock_get_traceparent_fields.return_value = ["00", "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7", "01"]
        ctx = self.hptc.extract(carrier)
        self.assertIsNone(ctx.correlation_id)
        self.assertIsNone(ctx.correlation_type)
        self.assertIsNone(ctx.instana_ancestor)
        self.assertEqual(ctx.level, 1)
        self.assertIsNone(ctx.long_trace_id)
        self.assertEqual(ctx.span_id, "1234567890abcdef")
        self.assertFalse(ctx.synthetic)
        self.assertEqual(ctx.trace_id, "1234d0e0e4736234")
        self.assertIsNone(ctx.trace_parent)
        self.assertEqual(ctx.traceparent, '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01')
        self.assertEqual(ctx.tracestate, 'congo=t61rcWkgMzE')