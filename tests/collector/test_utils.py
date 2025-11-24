# (c) Copyright IBM Corp. 2025


import pytest
from typing import Generator
from instana.collector.utils import format_span
from instana.singletons import get_tracer
from instana.span.registered_span import RegisteredSpan
from instana.span.span import get_current_span
from opentelemetry.trace.span import format_span_id

from instana.span_context import SpanContext


class TestUtils:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.span_context = None
        yield

    def test_format_span(self, span_context: SpanContext) -> None:
        self.span_context = span_context
        with self.tracer.start_as_current_span(
            name="span1", span_context=self.span_context
        ) as pspan:
            expected_trace_id = format_span_id(pspan.context.trace_id)
            expected_span_id = format_span_id(pspan.context.span_id)
            assert get_current_span() is pspan
            with self.tracer.start_as_current_span(name="span2") as cspan:
                assert get_current_span() is cspan
                assert cspan.parent_id == pspan.context.span_id
                span_list = [
                    RegisteredSpan(pspan, None, "log"),
                    RegisteredSpan(cspan, None, "log"),
                ]
        formatted_spans = format_span(span_list)
        assert len(formatted_spans) == 2
        assert formatted_spans[0].t == expected_trace_id
        assert formatted_spans[0].k == 1
        assert formatted_spans[0].s == expected_span_id
        assert formatted_spans[0].n == "span1"

        assert formatted_spans[1].t == expected_trace_id
        assert formatted_spans[1].p == formatted_spans[0].s
        assert formatted_spans[1].k == 1
        assert formatted_spans[1].s != formatted_spans[0].s
        assert formatted_spans[1].n == "span2"
