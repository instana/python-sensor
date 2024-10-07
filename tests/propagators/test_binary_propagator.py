# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from typing import Generator

import pytest
from opentelemetry.trace import (
    format_span_id,
    format_trace_id,
)

from instana.propagators.binary_propagator import BinaryPropagator
from instana.span_context import SpanContext
from instana.util.ids import hex_id


class TestBinaryPropagator:
    @pytest.fixture(autouse=True)
    def _resources(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        self.bp = BinaryPropagator()
        yield

    def test_inject_carrier_dict(self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str) -> None:
        carrier = {}
        ctx = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        carrier = self.bp.inject(ctx, carrier)

        assert carrier[b"x-instana-t"] == hex_trace_id.encode("utf-8")
        assert carrier[b"x-instana-s"] == hex_span_id.encode("utf-8")
        assert carrier[b"x-instana-l"] == b"1"
        assert carrier[b"server-timing"] == f"intid;desc={hex_id(trace_id)}".encode("utf-8")

    def test_inject_carrier_dict_w3c_True(self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str) -> None:
        carrier = {}
        ctx = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        carrier = self.bp.inject(ctx, carrier, disable_w3c_trace_context=False)

        assert carrier[b"x-instana-t"] == hex_trace_id.encode("utf-8")
        assert carrier[b"x-instana-s"] == hex_span_id.encode("utf-8")
        assert carrier[b"x-instana-l"] == b"1"
        assert carrier[b"server-timing"] == f"intid;desc={hex_id(trace_id)}".encode("utf-8")
        assert carrier[
            b"traceparent"
        ] == f"00-{format_trace_id(trace_id)}-{format_span_id(span_id)}-01".encode(
            "utf-8"
        )
        assert carrier[b"tracestate"] == f"in={hex_id(trace_id)};{hex_id(span_id)}".encode("utf-8")

    def test_inject_carrier_list(self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str) -> None:
        carrier = []
        ctx = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        carrier = self.bp.inject(ctx, carrier)

        assert isinstance(carrier, list)
        assert carrier[0] == (b"x-instana-t", hex_trace_id.encode("utf-8"))
        assert carrier[1] == (b"x-instana-s", hex_span_id.encode("utf-8"))
        assert carrier[2] == (b"x-instana-l", b"1")
        assert carrier[3] == (
            b"server-timing",
            f"intid;desc={hex_id(trace_id)}".encode("utf-8"),
        )

    def test_inject_carrier_list_w3c_True(self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str) -> None:
        carrier = []
        ctx = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        carrier = self.bp.inject(ctx, carrier, disable_w3c_trace_context=False)

        assert isinstance(carrier, list)
        assert carrier[0] == (
            b"traceparent",
            f"00-{format_trace_id(trace_id)}-{format_span_id(span_id)}-01".encode(
                "utf-8"
            ),
        )
        assert carrier[1] == (
            b"tracestate",
            f"in={hex_id(trace_id)};{hex_id(span_id)}".encode("utf-8"),
        )
        assert carrier[2] == (b"x-instana-t", hex_trace_id.encode("utf-8"))
        assert carrier[3] == (b"x-instana-s", hex_span_id.encode("utf-8"))
        assert carrier[4] == (b"x-instana-l", b"1")
        assert carrier[5] == (
            b"server-timing",
            f"intid;desc={hex_id(trace_id)}".encode("utf-8"),
        )

    def test_inject_carrier_tuple(self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str) -> None:
        carrier = ()
        ctx = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        carrier = self.bp.inject(ctx, carrier)

        assert isinstance(carrier, tuple)
        assert carrier[0] == (b"x-instana-t", hex_trace_id.encode("utf-8"))
        assert carrier[1] == (b"x-instana-s", hex_span_id.encode("utf-8"))
        assert carrier[2] == (b"x-instana-l", b"1")
        assert carrier[3] == (
            b"server-timing",
            f"intid;desc={hex_id(trace_id)}".encode("utf-8"),
        )

    def test_inject_carrier_tuple_w3c_True(self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str) -> None:
        carrier = ()
        ctx = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        carrier = self.bp.inject(ctx, carrier, disable_w3c_trace_context=False)

        assert isinstance(carrier, tuple)
        assert carrier[0] == (
            b"traceparent",
            f"00-{format_trace_id(trace_id)}-{format_span_id(span_id)}-01".encode(
                "utf-8"
            ),
        )
        assert carrier[1] == (
            b"tracestate",
            f"in={hex_id(trace_id)};{hex_id(span_id)}".encode("utf-8"),
        )
        assert carrier[2] == (b"x-instana-t", hex_trace_id.encode("utf-8"))
        assert carrier[3] == (b"x-instana-s", hex_span_id.encode("utf-8"))
        assert carrier[4] == (b"x-instana-l", b"1")
        assert carrier[5] == (
            b"server-timing",
            f"intid;desc={hex_id(trace_id)}".encode("utf-8"),
        )

    def test_inject_carrier_set_exception(self, trace_id: int, span_id: int) -> None:
        carrier = set()
        ctx = SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )
        carrier = self.bp.inject(ctx, carrier)
        assert not carrier
