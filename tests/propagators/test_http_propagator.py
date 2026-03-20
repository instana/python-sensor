# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import os
from typing import Any, Dict, Generator

import pytest
from opentelemetry.context.context import Context
from opentelemetry.trace import (
    INVALID_SPAN_ID,
    INVALID_TRACE_ID,
    format_span_id,
    format_trace_id,
)

from instana.propagators.http_propagator import HTTPPropagator
from instana.span.span import get_current_span
from instana.span_context import SpanContext
from instana.util.ids import header_to_long_id, internal_id


class TestHTTPPropagator:
    @pytest.fixture(autouse=True)
    def _resources(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        self.hptc = HTTPPropagator()
        yield
        # teardown
        # Clear the INSTANA_DISABLE_W3C_TRACE_CORRELATION environment variable
        os.environ["INSTANA_DISABLE_W3C_TRACE_CORRELATION"] = ""

    @pytest.fixture(scope="function")
    def _instana_long_tracer_id(self) -> str:
        return "4bf92f3577b34da6a3ce929d0e0e4736"

    @pytest.fixture(scope="function")
    def _instana_span_id(self) -> str:
        return "00f067aa0ba902b7"

    @pytest.fixture(scope="function")
    def _trace_id(self, _instana_long_tracer_id: str) -> int:
        return int(_instana_long_tracer_id[-16:], 16)

    @pytest.fixture(scope="function")
    def _span_id(self, _instana_span_id: str) -> int:
        return int(_instana_span_id, 16)

    @pytest.fixture(scope="function")
    def _long_tracer_id(self, _instana_long_tracer_id: str) -> int:
        return int(_instana_long_tracer_id, 16)

    @pytest.fixture(scope="function")
    def _traceparent(self, _instana_long_tracer_id: str, _instana_span_id: str) -> str:
        return f"00-{_instana_long_tracer_id}-{_instana_span_id}-01"

    @pytest.fixture(scope="function")
    def _tracestate(self) -> str:
        return "congo=t61rcWkgMzE"

    def test_extract_carrier_dict(
        self,
        trace_id: int,
        span_id: int,
        _instana_long_tracer_id: str,
        _instana_span_id: str,
        _trace_id: int,
        _span_id: int,
        _traceparent: str,
        _tracestate: str,
    ) -> None:
        carrier = {
            "traceparent": _traceparent,
            "tracestate": _tracestate,
            "X-INSTANA-T": f"{trace_id}",
            "X-INSTANA-S": f"{span_id}",
            "X-INSTANA-L": f"1, correlationType=web; correlationId={span_id}",
        }

        ctx = self.hptc.extract(carrier)
        span_ctx = get_current_span(ctx).get_span_context()

        assert span_ctx.correlation_id == str(span_id)
        assert span_ctx.correlation_type == "web"
        assert span_ctx.level == 1
        assert span_ctx.long_trace_id == header_to_long_id(_instana_long_tracer_id)
        assert span_ctx.span_id == _span_id
        assert span_ctx.trace_id == _trace_id
        assert span_ctx.trace_parent
        assert (
            span_ctx.traceparent
            == f"00-{_instana_long_tracer_id}-{_instana_span_id}-01"
        )
        assert span_ctx.tracestate == _tracestate
        assert not span_ctx.synthetic
        assert not span_ctx.instana_ancestor

    def test_extract_carrier_list(
        self,
        _trace_id: int,
        _span_id: int,
        _instana_long_tracer_id: str,
        _instana_span_id: str,
        _traceparent: str,
        _tracestate: str,
    ) -> None:
        _trace_id = str(_trace_id)
        carrier = [
            ("user-agent", "python-requests/2.23.0"),
            ("accept-encoding", "gzip, deflate"),
            ("accept", "*/*"),
            ("connection", "keep-alive"),
            ("traceparent", _traceparent),
            ("tracestate", _tracestate),
            ("X-INSTANA-T", f"{_trace_id}"),
            ("X-INSTANA-S", f"{_span_id}"),
            ("X-INSTANA-L", "1"),
        ]

        ctx = self.hptc.extract(carrier)
        span_ctx = get_current_span(ctx).get_span_context()

        assert not span_ctx.correlation_id
        assert not span_ctx.correlation_type
        assert not span_ctx.instana_ancestor
        assert span_ctx.level == 1
        assert not span_ctx.long_trace_id
        assert span_ctx.span_id == _span_id
        assert not span_ctx.synthetic
        assert span_ctx.trace_id == internal_id(_trace_id)
        assert not span_ctx.trace_parent
        assert (
            span_ctx.traceparent
            == f"00-{_instana_long_tracer_id}-{_instana_span_id}-01"
        )
        assert span_ctx.tracestate == _tracestate

    def test_extract_carrier_dict_validate_Exception_None_returned(
        self,
        trace_id: int,
        span_id: int,
        _tracestate: str,
    ) -> None:
        # In this test case, the traceparent header fails the validation, so
        # traceparent and tracestate are not used.
        # Additionally, because the correlation flags are present in the
        # 'X-INSTANA-L' header, we need to start a new SpanContext, and the
        # present values of 'X-INSTANA-T' and 'X-INSTANA-S' headers should not
        # be used.

        carrier = {
            "traceparent": "00-4gf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'",  # the long-trace-id is malformed to be invalid.
            "tracestate": _tracestate,
            "X-INSTANA-T": f"{trace_id}",
            "X-INSTANA-S": f"{span_id}",
            "X-INSTANA-L": f"1, correlationType=web; correlationId={span_id}",
        }

        ctx = self.hptc.extract(carrier)
        span_ctx = get_current_span(ctx).get_span_context()

        assert isinstance(ctx, Context)
        assert isinstance(span_ctx, SpanContext)
        assert span_ctx.trace_id == INVALID_TRACE_ID
        assert span_ctx.span_id == INVALID_SPAN_ID
        assert not span_ctx.synthetic
        assert span_ctx.correlation_id == str(span_id)
        assert span_ctx.correlation_type == "web"

    def test_extract_fake_exception(
        self,
        trace_id: int,
        span_id: int,
        _tracestate: str,
        mocker,
    ) -> None:
        carrier = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e-00f067aa0ba902b7-01",
            "tracestate": _tracestate,
            "X-INSTANA-T": f"{trace_id}",
            "X-INSTANA-S": f"{span_id}",
            "X-INSTANA-L": f"1, correlationType=web; correlationId={span_id}",
        }
        with pytest.raises(Exception):
            ctx = self.hptc.extract(carrier)
            assert not ctx

    def test_extract_carrier_dict_corrupted_level_header(
        self,
        trace_id: int,
        span_id: int,
        _instana_long_tracer_id: str,
        _trace_id: int,
        _span_id: int,
        _traceparent: str,
        _tracestate: str,
    ) -> None:
        # In this test case, the 'X-INSTANA-L' header is corrupted

        carrier = {
            "traceparent": _traceparent,
            "tracestate": _tracestate,
            "X-INSTANA-T": f"{trace_id}",
            "X-INSTANA-S": f"{span_id}",
            "X-INSTANA-L": f"1, correlationType=web; correlationId{span_id}",
        }

        ctx = self.hptc.extract(carrier)
        span_ctx = get_current_span(ctx).get_span_context()

        assert not span_ctx.correlation_id
        assert span_ctx.correlation_type == "web"
        assert not span_ctx.instana_ancestor
        assert span_ctx.level == 1
        assert span_ctx.long_trace_id == header_to_long_id(_instana_long_tracer_id)
        assert span_ctx.span_id == _span_id
        assert not span_ctx.synthetic
        assert span_ctx.trace_id == _trace_id
        assert span_ctx.trace_parent
        assert span_ctx.traceparent == _traceparent
        assert span_ctx.tracestate == _tracestate

    def test_extract_carrier_dict_level_header_not_splitable(
        self,
        _trace_id: int,
        _span_id: int,
        _traceparent: str,
        _tracestate: str,
    ) -> None:
        _trace_id = str(_trace_id)
        carrier = {
            "traceparent": _traceparent,
            "tracestate": _tracestate,
            "X-INSTANA-T": f"{_trace_id}",
            "X-INSTANA-S": f"{_span_id}",
            "X-INSTANA-L": ["1"],
        }

        ctx = self.hptc.extract(carrier)
        span_ctx = get_current_span(ctx).get_span_context()

        assert not span_ctx.correlation_id
        assert not span_ctx.correlation_type
        assert not span_ctx.instana_ancestor
        assert span_ctx.level == 1
        assert not span_ctx.long_trace_id
        assert span_ctx.span_id == _span_id
        assert not span_ctx.synthetic
        assert span_ctx.trace_id == internal_id(_trace_id)
        assert not span_ctx.trace_parent
        assert span_ctx.traceparent == _traceparent
        assert span_ctx.tracestate == _tracestate

    # The following tests are based on the test cases defined in the
    # tracer_compliance_test_cases.json file.
    #
    # Each line of the parametrize tuple correlates to a test case scenario:
    # - scenario 28: "Scenario/incoming headers": "w3c off, only X-INSTANA-L=0"
    # - scenario 29: "Scenario/incoming headers": "w3c off, X-INSTANA-L=0 plus -T and -S"
    # - scenario 30: "Scenario/incoming headers": "w3c off, X-INSTANA-L=0 plus traceparent"
    # - scenario 31: "Scenario/incoming headers": "w3c off, X-INSTANA-L=0 plus traceparent and tracestate",
    @pytest.mark.parametrize(
        "disable_w3c, carrier_header",
        [
            ("yes_please", {"X-INSTANA-L": "0"}),
            (
                "w3c_trace_correlation_stinks",
                {
                    "X-INSTANA-T": "11803532876627986230",
                    "X-INSTANA-S": "67667974448284343",
                    "X-INSTANA-L": "0",
                },
            ),
            (
                "w3c_trace_correlation_stinks",
                {
                    "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b9c7c989f97918e1-01",
                    "X-INSTANA-L": "0",
                },
            ),
            (
                "w3c_trace_correlation_stinks",
                {
                    "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b9c7c989f97918e1-01",
                    "tracestate": "congo=ucfJifl5GOE,rojo=00f067aa0ba902b7",
                    "X-INSTANA-L": "0",
                },
            ),
        ],
    )
    def test_w3c_off_x_instana_l_0(
        self,
        disable_w3c: str,
        carrier_header: Dict[str, Any],
        trace_id: int,
    ) -> None:
        os.environ["INSTANA_DISABLE_W3C_TRACE_CORRELATION"] = disable_w3c

        ctx = self.hptc.extract(carrier_header)
        span_ctx = get_current_span(ctx).get_span_context()

        # Assert the level is (zero) int, not str
        assert isinstance(span_ctx.level, int)
        assert span_ctx.level == 0

        # Assert the suppression is on
        assert span_ctx.suppression

        # Assert the rest of the attributes are on their default value
        assert span_ctx.trace_id == INVALID_TRACE_ID
        assert span_ctx.span_id == INVALID_SPAN_ID
        assert not span_ctx.synthetic
        assert not span_ctx.correlation_id
        assert not span_ctx.trace_parent
        assert not span_ctx.instana_ancestor
        assert not span_ctx.long_trace_id
        assert not span_ctx.correlation_type
        assert not span_ctx.correlation_id

        # Assert that the traceparent is propagated when it is enabled
        if "traceparent" in carrier_header.keys():
            assert span_ctx.traceparent
            tp_trace_id = header_to_long_id(carrier_header["traceparent"].split("-")[1])
        else:
            assert not span_ctx.traceparent
            tp_trace_id = span_ctx.trace_id

        # Assert that the tracestate is propagated when it is enabled
        if "tracestate" in carrier_header.keys():
            assert span_ctx.tracestate
        else:
            assert not span_ctx.tracestate

        # Simulate the side-effect of starting a span, getting a trace_id and span_id.
        # Actually, with OTel API using a Tuple to store the SpanContext info,
        # this will not change the values.
        span_ctx.trace_id = span_ctx.span_id = trace_id

        # Test propagation
        downstream_carrier = {}

        self.hptc.inject(span_ctx, downstream_carrier)

        # Assert the 'X-INSTANA-L' has been injected with the correct 0 value
        assert "X-INSTANA-L" in downstream_carrier
        assert downstream_carrier.get("X-INSTANA-L") == "0"

        assert "traceparent" in downstream_carrier
        assert (
            downstream_carrier.get("traceparent")
            == f"00-{format_trace_id(tp_trace_id)}-{format_span_id(span_ctx.span_id)}-00"
        )

        # Assert that the tracestate is propagated when it is enabled
        if "tracestate" in carrier_header.keys():
            assert "tracestate" in downstream_carrier
            assert carrier_header["tracestate"] == downstream_carrier["tracestate"]

    def test_suppression_when_child_level_is_lower(
        self,
        _trace_id: int,
        _span_id: int,
    ) -> None:
        """
        Test that span_context.level is updated when the child level (extracted from carrier) is lower than the
        current span_context.level.
        """
        # Create a span context with level=1
        original_span_context = SpanContext(
            trace_id=_trace_id,
            span_id=_span_id,
            is_remote=False,
            level=1,
        )

        # Create a carrier with level=0 (suppression)
        carrier_header = {"x-instana-l": "0"}

        # Inject the span context into the carrier
        self.hptc.inject(original_span_context, carrier_header)

        # Extract the span context from the carrier to verify the level was updated
        extracted_context = self.hptc.extract(carrier_header)
        span_ctx = get_current_span(extracted_context).get_span_context()

        # Verify that the level is 0 (suppressed)
        assert span_ctx.level == 0
        assert span_ctx.suppression

        # Create a new carrier to test the propagation
        downstream_carrier = {}

        # Inject the extracted context into the downstream carrier
        self.hptc.inject(span_ctx, downstream_carrier)

        # Verify that the downstream carrier has the correct level
        assert downstream_carrier.get("X-INSTANA-L") == "0"

        # Verify that no trace or span IDs are injected when suppressed
        assert "X-INSTANA-T" not in downstream_carrier
        assert "X-INSTANA-S" not in downstream_carrier
