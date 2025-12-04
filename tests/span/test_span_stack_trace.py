# (c) Copyright IBM Corp. 2025

"""Tests for stack trace collection functionality."""

from typing import Generator

import pytest

from instana.recorder import StanRecorder
from instana.span.span import InstanaSpan
from instana.span.stack_trace import add_stack, add_stack_trace_if_needed
from instana.span_context import SpanContext


class TestSpanStackTrace:
    """Test stack trace collection for spans."""

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.span = None
        yield
        if isinstance(self.span, InstanaSpan):
            self.span.events.clear()

    def test_add_stack_hard_limit(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that stack trace is capped at 40 frames even with higher limit."""
        span_name = "redis"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        # Manually set a high limit in options
        span_processor.agent.options.stack_trace_length = 50
        
        # Call add_stack directly with is_errored=False
        stack = add_stack(
            level=span_processor.agent.options.stack_trace_level,
            limit=span_processor.agent.options.stack_trace_length,
            is_errored=False
        )

        # Check if default is set
        assert span_processor.agent.options.stack_trace_level == "all"

        assert stack
        assert len(stack) <= 40  # Hard cap at 40

        stack_0 = stack[0]
        assert len(stack_0) == 3
        assert "c" in stack_0.keys()
        assert "n" in stack_0.keys()
        assert "m" in stack_0.keys()

    def test_add_stack_level_all(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test stack trace collection with level='all'."""
        span_name = "http"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        span_processor.agent.options.stack_trace_level = "all"
        test_limit = 5
        span_processor.agent.options.stack_trace_length = test_limit
        
        # Non-errored span should get stack trace
        stack = add_stack(
            level=span_processor.agent.options.stack_trace_level,
            limit=span_processor.agent.options.stack_trace_length,
            is_errored=False
        )

        assert stack
        assert len(stack) <= test_limit

    def test_add_stack_level_error_not_errored(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that non-errored spans don't get stack trace with level='error'."""
        span_name = "http"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        span_processor.agent.options.stack_trace_level = "error"
        span_processor.agent.options.stack_trace_length = 35
        
        # Non-errored span should NOT get stack trace
        stack = add_stack(
            level=span_processor.agent.options.stack_trace_level,
            limit=span_processor.agent.options.stack_trace_length,
            is_errored=False
        )

        assert stack is None

    def test_add_stack_level_error_errored(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that errored spans get full stack trace with level='error'."""
        span_name = "http"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        span_processor.agent.options.stack_trace_level = "error"
        test_limit = 10
        span_processor.agent.options.stack_trace_length = test_limit
        
        # Errored span should get FULL stack trace (no limit)
        stack = add_stack(
            level=span_processor.agent.options.stack_trace_level,
            limit=span_processor.agent.options.stack_trace_length,
            is_errored=True
        )

        assert stack
        # Should have more than the configured limit since it's errored
        assert len(stack) >= test_limit

    def test_add_stack_level_none(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that no stack trace is collected with level='none'."""
        span_name = "http"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        span_processor.agent.options.stack_trace_level = "none"
        span_processor.agent.options.stack_trace_length = 20
        
        # Should NOT get stack trace
        stack = add_stack(
            level=span_processor.agent.options.stack_trace_level,
            limit=span_processor.agent.options.stack_trace_length,
            is_errored=False
        )
        assert stack is None
        
        # Even errored spans should not get stack trace
        stack = add_stack(
            level=span_processor.agent.options.stack_trace_level,
            limit=span_processor.agent.options.stack_trace_length,
            is_errored=True
        )
        assert stack is None

    def test_add_stack_errored_span_full_stack(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that errored spans get full stack regardless of level setting."""
        span_name = "mysql"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        # Set level to 'all' with a low limit
        span_processor.agent.options.stack_trace_level = "all"
        test_limit = 5
        span_processor.agent.options.stack_trace_length = test_limit
        
        # Errored span should get FULL stack (not limited to 5)
        stack = add_stack(
            level=span_processor.agent.options.stack_trace_level,
            limit=span_processor.agent.options.stack_trace_length,
            is_errored=True
        )

        assert stack
        # Should have more than the configured limit since it's errored
        assert len(stack) > test_limit

    def test_add_stack_trace_if_needed_exit_span(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test add_stack_trace_if_needed for EXIT spans."""
        span_name = "redis"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        # Call the function that checks if it's an EXIT span
        add_stack_trace_if_needed(self.span)

        assert self.span.stack

    def test_add_stack_trace_if_needed_non_exit_span(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test add_stack_trace_if_needed for non-EXIT spans."""
        span_name = "wsgi"  # Not an EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        # Call the function - should not add stack for non-EXIT spans
        add_stack_trace_if_needed(self.span)

        assert not self.span.stack

    def test_add_stack_trace_if_needed_errored_span(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test add_stack_trace_if_needed detects errored spans."""
        span_name = "httpx"  # EXIT span
        attributes = {"ec": 1}  # Mark as errored
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )
        
        test_limit = 5
        span_processor.agent.options.stack_trace_length = test_limit
        
        # Call the function - should detect error and use full stack
        add_stack_trace_if_needed(self.span)

        assert self.span.stack
        # Should have more than limit since it's errored
        assert len(self.span.stack) > test_limit

    def test_span_end_collects_stack_trace(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that span.end() triggers stack trace collection for EXIT spans."""
        span_name = "urllib3"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        assert not self.span.stack
        
        # End the span - should trigger stack trace collection
        self.span.end()

        assert self.span.stack
        assert self.span.end_time

    def test_stack_frame_format(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that stack frames have correct format."""
        span_name = "postgres"  # EXIT span
        self.span = InstanaSpan(span_name, span_context, span_processor)
        
        test_limit = 5
        span_processor.agent.options.stack_trace_length = test_limit
        
        # Use add_stack directly
        stack = add_stack(
            level=span_processor.agent.options.stack_trace_level,
            limit=span_processor.agent.options.stack_trace_length,
            is_errored=False
        )

        assert stack
        for frame in stack:
            assert isinstance(frame, dict)
            assert "c" in frame  # file path
            assert "n" in frame  # line number
            assert "m" in frame  # method name
            assert isinstance(frame["c"], str)
            assert isinstance(frame["n"], int)
            assert isinstance(frame["m"], str)
