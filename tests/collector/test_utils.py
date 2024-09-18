import pytest
from typing import Generator
from instana.collector.utils import format_span
from instana.singletons import tracer
from instana.span.registered_span import RegisteredSpan
from instana.span.span import InstanaSpan
from opentelemetry.trace.span import format_span_id


class TestUtils:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.recorder = tracer.span_processor
        yield

    def test_format_span(self, trace_id, span_id, span_context, span_processor) -> None:
        expected_trace_id = format_span_id(trace_id)
        expected_span_id = format_span_id(span_id)
        span_list = [
            RegisteredSpan(
                InstanaSpan("span1", span_context, span_processor), None, "log"
            ),
            RegisteredSpan(
                InstanaSpan("span2", span_context, span_processor), None, "log"
            ),
            RegisteredSpan(
                InstanaSpan("span3", span_context, span_processor), None, "log"
            ),
        ]
        formatted_spans = format_span(span_list)
        assert len(formatted_spans) == 3
        assert formatted_spans[0].t == expected_trace_id
        assert formatted_spans[0].s == expected_span_id
        assert formatted_spans[0].n == "span1"
