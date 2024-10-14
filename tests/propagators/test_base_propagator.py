# (c) Copyright IBM Corp. 2024

from typing import Generator
from unittest.mock import Mock

import pytest

from instana.propagators.base_propagator import BasePropagator


class TestBasePropagator:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.propagator = BasePropagator()
        yield
        self.propagator = None

    def test_extract_headers_dict(self) -> None:
        carrier_as_a_dict = {"key": "value"}
        assert carrier_as_a_dict == self.propagator.extract_headers_dict(
            carrier_as_a_dict
        )
        mocked_carrier = Mock()
        mocked_carrier.__dict__ = carrier_as_a_dict
        assert carrier_as_a_dict == self.propagator.extract_headers_dict(mocked_carrier)
        wrong_carrier = "value"
        assert self.propagator.extract_headers_dict(wrong_carrier) is None

    def test_get_ctx_level(self) -> None:
        assert 3 == self.propagator._get_ctx_level("3,4")
        assert 1 == self.propagator._get_ctx_level("wrong_data")

    def test_get_correlation_properties(self) -> None:
        a, b = self.propagator._get_correlation_properties(
            ",correlationType=3;correlationId=5;"
        )
        assert a == "3"
        assert b == "5"
        assert "3", None == self.propagator._get_correlation_properties(  # noqa: E711
            ",correlationType=3;"
        )

    def test_get_participating_trace_context(self, span_context) -> None:
        traceparent, tracestate = self.propagator._get_participating_trace_context(
            span_context
        )
        assert traceparent == "00-00000000000000001926b88ec9ee75ab-5fb1cff576b7e2f5-01"
        assert tracestate == "in=1926b88ec9ee75ab;5fb1cff576b7e2f5"

    def test_extract_instana_headers(self) -> None:
        dc = {
            "x-instana-t": "123456789",
            "x-instana-s": "12345",
            "x-instana-l": str.encode(",correlationType=3;correlationId=5;"),
            "x-instana-synthetic": "1",
        }
        trace_id, span_id, level, synthetic = self.propagator.extract_instana_headers(
            dc=dc
        )
        assert trace_id == "123456789"
        assert span_id == "12345"
        assert level == ",correlationType=3;correlationId=5;"
        assert synthetic

    def test_extract(self) -> None:
        carrier = {
            "x-instana-t": "123456789",
            "x-instana-s": "12345",
            "x-instana-l": str.encode("3,correlationId=5;"),
            "x-instana-synthetic": "1",
            "traceparent": "00-1812338823475918251-6895521157646639861-01",
            "tracestate": "in=1812338823475918251;6895521157646639861",
        }
        span_context = self.propagator.extract(
            carrier=carrier, disable_w3c_trace_context=True
        )
        assert span_context
        span_context = self.propagator.extract(carrier=carrier)
        span_context = self.propagator.extract(
            carrier=None, disable_w3c_trace_context=True
        )
        assert not span_context
        carrier.pop("x-instana-t", None)
        carrier.pop("x-instana-s", None)
        span_context = self.propagator.extract(carrier=carrier)
        assert span_context
        carrier = {
            "x-instana-t": "123456789",
            "x-instana-s": "12345",
            "x-instana-l": "2,correlationType=3;correlationId=5;",
            "x-instana-synthetic": "1",
            "traceparent": "00-4bf92f3577b34da61234567899999999-1234567890888888-01",
            "tracestate": "in=1812338823475918251;6895521157646639861",
        }
        span_context = self.propagator.extract(carrier=carrier)
        assert span_context
