# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.propagators.http_propagator import HTTPPropagator
from instana.w3c_trace_context.traceparent import Traceparent
from instana.span_context import SpanContext
from mock import patch
import os
import unittest


class TestHTTPPropagatorTC(unittest.TestCase):
    def setUp(self):
        self.hptc = HTTPPropagator()

    def tearDown(self):
        """ Clear the INSTANA_DISABLE_W3C_TRACE_CORRELATION environment variable """
        os.environ["INSTANA_DISABLE_W3C_TRACE_CORRELATION"] = ""

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


    # 28 in the tracer_compliance_test_cases.json
    # "Scenario/incoming headers": "w3c off, only X-INSTANA-L=0",
    def test_w3c_off_only_x_instana_l_0(self):
        carrier = {
            'X-INSTANA-L': '0'
        }
        os.environ['INSTANA_DISABLE_W3C_TRACE_CORRELATION'] = 'yes_please'
        ctx = self.hptc.extract(carrier)

        # Assert that the level is (zero) int, not str
        self.assertEqual(ctx.level, 0)
        # Assert that the suppression is on
        self.assertTrue(ctx.suppression)

        # Assert that the rest of the attributes are on their default value
        self.assertTrue(ctx.sampled)
        self.assertFalse(ctx.synthetic)
        self.assertEqual(ctx._baggage, {})

        self.assertTrue(
                all(map(lambda x: x is None,
                    (ctx.correlation_id, ctx.trace_id, ctx.span_id,
                     ctx.trace_parent, ctx.instana_ancestor,
                     ctx.long_trace_id, ctx.correlation_type,
                     ctx.correlation_id, ctx.traceparent, ctx.tracestate)
            )))

        # Simulate the sideffect of starting a span,
        # getting a trace_id and span_id:
        ctx.trace_id = ctx.span_id = '4dfe94d65496a02c'

        # Test propagation
        downstream_carrier = {}

        self.hptc.inject(ctx, downstream_carrier)

        # Assert that 'X-INSTANA-L' has been injected with the correct 0 value
        self.assertIn('X-INSTANA-L', downstream_carrier)
        self.assertEqual(downstream_carrier.get('X-INSTANA-L'), '0')

        self.assertIn('traceparent', downstream_carrier)
        self.assertEqual('00-0000000000000000' + ctx.trace_id + '-' + ctx.span_id + '-00',
                         downstream_carrier.get('traceparent'))


    # 29 in the tracer_compliance_test_cases.json
    # "Scenario/incoming headers": "w3c off, X-INSTANA-L=0 plus -T and -S",
    def test_w3c_off_x_instana_l_0_plus_t_and_s(self):
        os.environ['INSTANA_DISABLE_W3C_TRACE_CORRELATION'] = 'w3c_trace_correlation_stinks'
        carrier = {
            'X-INSTANA-T': 'fa2375d711a4ca0f',
            'X-INSTANA-S': '37cb2d6e9b1c078a',
            'X-INSTANA-L': '0'
        }

        ctx = self.hptc.extract(carrier)

        # Assert that the level is (zero) int, not str
        self.assertEqual(ctx.level, 0)
        # Assert that the suppression is on
        self.assertTrue(ctx.suppression)

        # Assert that the rest of the attributes are on their default value
        # And even T and S are None
        self.assertTrue(ctx.sampled)
        self.assertFalse(ctx.synthetic)
        self.assertEqual(ctx._baggage, {})

        self.assertTrue(
                all(map(lambda x: x is None,
                    (ctx.correlation_id, ctx.trace_id, ctx.span_id,
                     ctx.trace_parent, ctx.instana_ancestor,
                     ctx.long_trace_id, ctx.correlation_type,
                     ctx.correlation_id, ctx.traceparent, ctx.tracestate)
            )))

        # Simulate the sideffect of starting a span,
        # getting a trace_id and span_id:
        ctx.trace_id = ctx.span_id = '4dfe94d65496a02c'

        # Test propagation
        downstream_carrier = {}

        self.hptc.inject(ctx, downstream_carrier)

        # Assert that 'X-INSTANA-L' has been injected with the correct 0 value
        self.assertIn('X-INSTANA-L', downstream_carrier)
        self.assertEqual(downstream_carrier.get('X-INSTANA-L'), '0')

        self.assertIn('traceparent', downstream_carrier)
        self.assertEqual('00-0000000000000000' + ctx.trace_id + '-' + ctx.span_id + '-00',
                         downstream_carrier.get('traceparent'))



    # 30 in the tracer_compliance_test_cases.json
    # "Scenario/incoming headers": "w3c off, X-INSTANA-L=0 plus traceparent",
    def test_w3c_off_x_instana_l_0_plus_traceparent(self):
        os.environ['INSTANA_DISABLE_W3C_TRACE_CORRELATION'] = 'w3c_trace_correlation_stinks'
        carrier = {
            'traceparent': '00-0af7651916cd43dd8448eb211c80319c-b9c7c989f97918e1-01',
            'X-INSTANA-L': '0'
        }

        ctx = self.hptc.extract(carrier)

        # Assert that the level is (zero) int, not str
        self.assertEqual(ctx.level, 0)
        # Assert that the suppression is on
        self.assertTrue(ctx.suppression)
        # Assert that the traceparent is not None
        self.assertIsNotNone(ctx.traceparent)

        # Assert that the rest of the attributes are on their default value
        self.assertTrue(ctx.sampled)
        self.assertFalse(ctx.synthetic)
        self.assertEqual(ctx._baggage, {})

        self.assertTrue(
                all(map(lambda x: x is None,
                    (ctx.correlation_id, ctx.trace_id, ctx.span_id,
                     ctx.instana_ancestor, ctx.long_trace_id, ctx.correlation_type,
                     ctx.correlation_id, ctx.tracestate)
            )))

        # Simulate the sideffect of starting a span,
        # getting a trace_id and span_id:
        ctx.trace_id = ctx.span_id = '4dfe94d65496a02c'

        # Test propagation
        downstream_carrier = {}
        self.hptc.inject(ctx, downstream_carrier)

        # Assert that 'X-INSTANA-L' has been injected with the correct 0 value
        self.assertIn('X-INSTANA-L', downstream_carrier)
        self.assertEqual(downstream_carrier.get('X-INSTANA-L'), '0')
        # Assert that the traceparent is propagated
        self.assertIn('traceparent', downstream_carrier)
        self.assertEqual('00-0af7651916cd43dd8448eb211c80319c-' + ctx.trace_id + '-00',
                         downstream_carrier.get('traceparent'))


    # 31 in the tracer_compliance_test_cases.json
    # "Scenario/incoming headers": "w3c off, X-INSTANA-L=0 plus traceparent and tracestate",
    def test_w3c_off_x_instana_l_0_plus_traceparent_and_tracestate(self):
        os.environ['INSTANA_DISABLE_W3C_TRACE_CORRELATION'] = 'w3c_trace_correlation_stinks'
        carrier = {
            'traceparent': '00-0af7651916cd43dd8448eb211c80319c-b9c7c989f97918e1-01',
            'tracestate': 'congo=ucfJifl5GOE,rojo=00f067aa0ba902b7',
            'X-INSTANA-L': '0'
        }

        ctx = self.hptc.extract(carrier)

        # Assert that the level is (zero) int, not str
        self.assertEqual(ctx.level, 0)
        # Assert that the suppression is on
        self.assertTrue(ctx.suppression)
        # Assert that the traceparent is not None
        self.assertIsNotNone(ctx.traceparent)

        # Assert that the rest of the attributes are on their default value
        self.assertTrue(ctx.sampled)
        self.assertFalse(ctx.synthetic)
        self.assertEqual(ctx._baggage, {})

        self.assertTrue(
                all(map(lambda x: x is None,
                    (ctx.correlation_id, ctx.trace_id, ctx.span_id,
                     ctx.instana_ancestor, ctx.long_trace_id, ctx.correlation_type,
                     ctx.correlation_id)
            )))

        # Simulate the sideffect of starting a span,
        # getting a trace_id and span_id:
        ctx.trace_id = ctx.span_id = '4dfe94d65496a02c'

        # Test propagation
        downstream_carrier = {}
        self.hptc.inject(ctx, downstream_carrier)

        # Assert that 'X-INSTANA-L' has been injected with the correct 0 value
        self.assertIn('X-INSTANA-L', downstream_carrier)
        self.assertEqual(downstream_carrier.get('X-INSTANA-L'), '0')
        # Assert that the traceparent is propagated
        self.assertIn('traceparent', downstream_carrier)
        self.assertEqual('00-0af7651916cd43dd8448eb211c80319c-' + ctx.trace_id + '-00',
                         downstream_carrier.get('traceparent'))
        # Assert that the tracestate is propagated
        self.assertIn('tracestate', downstream_carrier)
        self.assertEqual(carrier['tracestate'], downstream_carrier['tracestate'])
