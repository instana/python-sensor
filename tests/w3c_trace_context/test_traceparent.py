# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.w3c_trace_context.traceparent import Traceparent
import unittest
from instana.util.ids import header_to_long_id, header_to_id

class TestTraceparent(unittest.TestCase):
    def setUp(self):
        self.tp = Traceparent()
        self.w3cTraceId = "4bf92f3577b34da6a3ce929d0e0e4736"

    def test_validate_valid(self):
        traceparent = f"00-{self.w3cTraceId}-00f067aa0ba902b7-01"
        self.assertEqual(traceparent, self.tp.validate(traceparent))

    def test_validate_newer_version(self):
        # Although the incoming traceparent header sports a newer version number, we should still be able to parse the
        # parts that we understand (and consider it valid).
        traceparent = f"fe-{self.w3cTraceId}-00f067aa0ba902b7-01-12345-abcd"
        self.assertEqual(traceparent, self.tp.validate(traceparent))

    def test_validate_unknown_flags(self):
        traceparent = f"00-{self.w3cTraceId}-00f067aa0ba902b7-ee"
        self.assertEqual(traceparent, self.tp.validate(traceparent))

    def test_validate_invalid_traceparent_version(self):
        traceparent = f"ff-{self.w3cTraceId}-00f067aa0ba902b7-01"
        self.assertIsNone(self.tp.validate(traceparent))

    def test_validate_invalid_traceparent(self):
        traceparent = "00-4bxxxxx3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        self.assertIsNone(self.tp.validate(traceparent))

    def test_validate_traceparent_None(self):
        traceparent = None
        self.assertIsNone(self.tp.validate(traceparent))

    def test_get_traceparent_fields(self):
        traceparent = f"00-{self.w3cTraceId}-00f067aa0ba902b7-01"
        version, trace_id, parent_id, sampled_flag = self.tp.get_traceparent_fields(traceparent)
        self.assertEqual(trace_id, header_to_long_id(self.w3cTraceId))
        self.assertEqual(parent_id, 67667974448284343)
        self.assertTrue(sampled_flag)

    def test_get_traceparent_fields_unsampled(self):
        traceparent = f"00-{self.w3cTraceId}-00f067aa0ba902b7-00"
        version, trace_id, parent_id, sampled_flag = self.tp.get_traceparent_fields(traceparent)
        self.assertEqual(trace_id, header_to_long_id(self.w3cTraceId))
        self.assertEqual(parent_id, 67667974448284343)
        self.assertFalse(sampled_flag)

    def test_get_traceparent_fields_newer_version(self):
        # Although the incoming traceparent header sports a newer version number, we should still be able to parse the
        # parts that we understand (and consider it valid).
        traceparent = f"fe-{self.w3cTraceId}-00f067aa0ba902b7-01-12345-abcd"
        version, trace_id, parent_id, sampled_flag = self.tp.get_traceparent_fields(traceparent)
        self.assertEqual(trace_id, header_to_long_id(self.w3cTraceId))
        self.assertEqual(parent_id, 67667974448284343)
        self.assertTrue(sampled_flag)

    def test_get_traceparent_fields_unknown_flags(self):
        traceparent = f"00-{self.w3cTraceId}-00f067aa0ba902b7-ff"
        version, trace_id, parent_id, sampled_flag = self.tp.get_traceparent_fields(traceparent)
        self.assertEqual(trace_id, header_to_long_id(self.w3cTraceId))
        self.assertEqual(parent_id, 67667974448284343)
        self.assertTrue(sampled_flag)

    def test_get_traceparent_fields_None_input(self):
        traceparent = None
        version, trace_id, parent_id, sampled_flag = self.tp.get_traceparent_fields(traceparent)
        self.assertIsNone(trace_id)
        self.assertIsNone(parent_id)
        self.assertFalse(sampled_flag)

    def test_get_traceparent_fields_string_input_no_dash(self):
        traceparent = "invalid"
        version, trace_id, parent_id, sampled_flag = self.tp.get_traceparent_fields(traceparent)
        self.assertIsNone(trace_id)
        self.assertIsNone(parent_id)
        self.assertFalse(sampled_flag)

    def test_update_traceparent(self):
        traceparent = f"00-{self.w3cTraceId}-00f067aa0ba902b7-01"
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "1234567890abcdef"
        level = 1
        expected_traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-1234567890abcdef-01"
        self.assertEqual(expected_traceparent, self.tp.update_traceparent(traceparent, in_trace_id, header_to_id(in_span_id), level))

    def test_update_traceparent_None(self):
        traceparent = None
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "7890abcdef"
        level = 0
        expected_traceparent = "00-00000000000000001234d0e0e4736234-0000007890abcdef-00"
        self.assertEqual(expected_traceparent, self.tp.update_traceparent(traceparent, in_trace_id, header_to_id(in_span_id), level))
