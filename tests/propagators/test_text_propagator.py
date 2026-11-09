# (c) Copyright IBM Corp. 2026

from typing import Generator
from unittest.mock import patch

import pytest

from instana.propagators.base_propagator import BasePropagator
from instana.propagators.text_propagator import TextPropagator
from instana.span_context import SpanContext
from instana.util.ids import hex_id


class TestTextPropagator:
    @pytest.fixture(autouse=True)
    def _resources(self) -> Generator[None, None, None]:
        self.tp = TextPropagator()
        yield

    @staticmethod
    def _ctx(trace_id: int, span_id: int) -> SpanContext:
        return SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            is_remote=False,
            level=1,
            baggage={},
            sampled=True,
            synthetic=False,
        )

    def test_inject_dict(
        self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str
    ) -> None:
        carrier = self.tp.inject(self._ctx(trace_id, span_id), {})
        assert carrier["x-instana-t"] == hex_trace_id
        assert carrier["x-instana-s"] == hex_span_id
        assert carrier["x-instana-l"] == "1"
        assert carrier["server-timing"] == f"intid;desc={hex_id(trace_id)}".encode()

    def test_inject_list(
        self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str
    ) -> None:
        carrier = self.tp.inject(self._ctx(trace_id, span_id), [])
        assert carrier[0] == ("x-instana-t", hex_trace_id)
        assert carrier[1] == ("x-instana-s", hex_span_id)
        assert carrier[2] == ("x-instana-l", "1")
        assert carrier[3] == (
            "server-timing",
            f"intid;desc={hex_id(trace_id)}".encode(),
        )

    def test_inject_tuple(
        self, trace_id: int, span_id: int, hex_trace_id: str, hex_span_id: str
    ) -> None:
        carrier = self.tp.inject(self._ctx(trace_id, span_id), ())
        assert isinstance(carrier, tuple)
        assert carrier[0] == ("x-instana-t", hex_trace_id)
        assert carrier[1] == ("x-instana-s", hex_span_id)
        assert carrier[2] == ("x-instana-l", "1")
        assert carrier[3] == (
            "server-timing",
            f"intid;desc={hex_id(trace_id)}".encode(),
        )

    def test_inject_setitem_carrier(self, trace_id: int, span_id: int) -> None:
        class Carrier:
            def __init__(self) -> None:
                self.items = {}

            def __setitem__(self, key, value) -> None:
                self.items[key] = value

        carrier = Carrier()
        self.tp.inject(self._ctx(trace_id, span_id), carrier)
        assert "x-instana-t" in carrier.items
        assert "server-timing" in carrier.items

    def test_inject_unsupported_carrier(self, trace_id: int, span_id: int) -> None:
        assert not self.tp.inject(self._ctx(trace_id, span_id), set())

    def test_inject_dict_server_timing_disabled(
        self, trace_id: int, span_id: int, hex_trace_id: str
    ) -> None:
        with patch.object(
            BasePropagator, "is_server_timing_disabled", return_value=True
        ):
            carrier = self.tp.inject(self._ctx(trace_id, span_id), {})
        assert carrier["x-instana-t"] == hex_trace_id
        assert "server-timing" not in carrier

    def test_inject_list_server_timing_disabled(
        self, trace_id: int, span_id: int
    ) -> None:
        with patch.object(
            BasePropagator, "is_server_timing_disabled", return_value=True
        ):
            carrier = self.tp.inject(self._ctx(trace_id, span_id), [])
        assert len(carrier) == 3
        assert all(key != "server-timing" for key, _ in carrier)

    def test_inject_tuple_server_timing_disabled(
        self, trace_id: int, span_id: int
    ) -> None:
        with patch.object(
            BasePropagator, "is_server_timing_disabled", return_value=True
        ):
            carrier = self.tp.inject(self._ctx(trace_id, span_id), ())
        assert len(carrier) == 3
        assert all(key != "server-timing" for key, _ in carrier)

    def test_inject_setitem_server_timing_disabled(
        self, trace_id: int, span_id: int
    ) -> None:
        class Carrier:
            def __init__(self) -> None:
                self.items = {}

            def __setitem__(self, key, value) -> None:
                self.items[key] = value

        carrier = Carrier()
        with patch.object(
            BasePropagator, "is_server_timing_disabled", return_value=True
        ):
            self.tp.inject(self._ctx(trace_id, span_id), carrier)
        assert "x-instana-t" in carrier.items
        assert "server-timing" not in carrier.items
