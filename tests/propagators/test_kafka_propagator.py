# (c) Copyright IBM Corp. 2025

import logging
from typing import Generator

import pytest
from mock import patch
from opentelemetry.trace.span import format_span_id

from instana.propagators.kafka_propagator import KafkaPropagator
from instana.span_context import SpanContext


class TestKafkaPropagator:
    @pytest.fixture(autouse=True)
    def _resources(self) -> Generator[None, None, None]:
        self.kafka_prop = KafkaPropagator()
        yield

    def test_extract_carrier_headers_as_list_of_dicts(self) -> None:
        carrier_as_a_list = [{"key": "value"}]
        response = self.kafka_prop.extract_carrier_headers(carrier_as_a_list)

        assert response == {"key": "value"}

        carrier_as_a_list = [{"key": "value"}, {"key": "value2"}]
        response = self.kafka_prop.extract_carrier_headers(carrier_as_a_list)

        assert response == {"key": "value2"}

    def test_extract_carrier_headers_as_list_of_tuples(self) -> None:
        carrier_as_a_list = [("key", "value")]
        response = self.kafka_prop.extract_carrier_headers(carrier_as_a_list)

        assert response == {"key": "value"}

        carrier_as_a_list = [("key", "value"), ("key", "value2")]
        response = self.kafka_prop.extract_carrier_headers(carrier_as_a_list)

        assert response == {"key": "value2"}

    def test_extract_carrier_headers_as_dict(self) -> None:
        carrier_as_a_dict = {"key": "value"}
        response = self.kafka_prop.extract_carrier_headers(carrier_as_a_dict)

        assert response == {"key": "value"}

    def test_extract_carrier_headers_as_set(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        carrier_as_a_dict = {"key": "value"}
        with patch.object(
            KafkaPropagator,
            "extract_headers_dict",
            side_effect=Exception(),
        ):
            response = self.kafka_prop.extract_carrier_headers(carrier_as_a_dict)

            assert not response
            assert (
                "kafka_propagator extract_headers_list: Couldn't convert - {'key': 'value'}"
                in caplog.messages
            )

    def test_extract(self) -> None:
        carrier_as_a_dict = {"key": "value"}
        disable_w3c_trace_context = False
        response = self.kafka_prop.extract(carrier_as_a_dict, disable_w3c_trace_context)
        assert response

    def test_extract_with_error(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        carrier_as_a_dict = {"key": "value"}
        disable_w3c_trace_context = False
        with patch.object(
            KafkaPropagator,
            "extract_carrier_headers",
            side_effect=Exception("fake error"),
        ):
            response = self.kafka_prop.extract(
                carrier_as_a_dict, disable_w3c_trace_context
            )
            assert not response
            assert "kafka_propagator extract error: fake error"

    def test_inject_without_suppression(self, trace_id: int, span_id: int) -> None:
        span_context = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        trace_id = span_context.trace_id
        span_id = span_context.span_id
        carrier = {}

        self.kafka_prop.inject(span_context, carrier)
        assert carrier == {
            "x_instana_l_s": b"1",
            "x_instana_t": format_span_id(trace_id).encode("utf-8"),
            "x_instana_s": format_span_id(span_id).encode("utf-8"),
        }

    def test_inject_with_suppression(self, trace_id: int, span_id: int) -> None:
        span_context = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        trace_id = span_context.trace_id
        span_id = span_context.span_id
        carrier = {"x_instana_l_s": "0"}

        self.kafka_prop.inject(span_context, carrier)
        assert carrier == {"x_instana_l_s": b"0"}
