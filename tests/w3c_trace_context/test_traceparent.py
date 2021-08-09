# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.w3c_trace_context.traceparent import Traceparent
import unittest


class TestTraceparent(unittest.TestCase):
    def setUp(self):
        self.tp = Traceparent()

    def test_validate_valid(self):
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        self.assertEqual(traceparent, self.tp.validate(traceparent))

    def test_validate_invalid_traceparent(self):
        traceparent = "00-4bxxxxx3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        self.assertIsNone(self.tp.validate(traceparent))

    def test_validate_traceparent_None(self):
        traceparent = None
        self.assertIsNone(self.tp.validate(traceparent))

    def test_get_traceparent_fields(self):
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        version, trace_id, parent_id, trace_flags = self.tp.get_traceparent_fields(traceparent)
        self.assertEqual(trace_id, "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertEqual(parent_id, "00f067aa0ba902b7")

    def test_get_traceparent_fields_None_input(self):
        traceparent = None
        version, trace_id, parent_id, trace_flags = self.tp.get_traceparent_fields(traceparent)
        self.assertIsNone(trace_id)
        self.assertIsNone(parent_id)

    def test_get_traceparent_fields_string_input_no_dash(self):
        traceparent = "invalid"
        version, trace_id, parent_id, trace_flags = self.tp.get_traceparent_fields(traceparent)
        self.assertIsNone(trace_id)
        self.assertIsNone(parent_id)

    def test_update_traceparent(self):
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "1234567890abcdef"
        level = 1
        expected_traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-1234567890abcdef-01"
        self.assertEqual(expected_traceparent, self.tp.update_traceparent(traceparent, in_trace_id, in_span_id, level))

    def test_update_traceparent_None(self):
        traceparent = None
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "7890abcdef"
        level = 0
        expected_traceparent = "00-00000000000000001234d0e0e4736234-0000007890abcdef-00"
        self.assertEqual(expected_traceparent, self.tp.update_traceparent(traceparent, in_trace_id, in_span_id, level))
