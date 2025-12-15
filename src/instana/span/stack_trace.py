# (c) Copyright IBM Corp. 2025

"""
Stack trace collection functionality for spans.

This module provides utilities for capturing and filtering stack traces
for EXIT spans based on configuration settings.
"""

import os
import re
import traceback
from typing import List, Optional, TYPE_CHECKING

from instana.log import logger
from instana.span.kind import EXIT_SPANS

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan

# Regex patterns for filtering Instana internal frames
_re_tracer_frame = re.compile(r"/instana/.*\.py$")
_re_with_stan_frame = re.compile("with_instana")


def _should_collect_stack(level: str, is_errored: bool) -> bool:
    """
    Determine if stack trace should be collected based on level and error state.
    
    Args:
        level: Stack trace collection level ("all", "error", or "none")
        is_errored: Whether the span has errors (ec > 0)
    
    Returns:
        True if stack trace should be collected, False otherwise
    """
    if level == "all":
        return True
    if level == "error" and is_errored:
        return True
    return False


def _should_exclude_frame(frame) -> bool:
    """
    Check if a frame should be excluded from the stack trace.
    
    Frames are excluded if they are part of Instana's internal code,
    unless INSTANA_DEBUG is set.
    
    Args:
        frame: A frame from traceback.extract_stack()
    
    Returns:
        True if frame should be excluded, False otherwise
    """
    if "INSTANA_DEBUG" in os.environ:
        return False
    if _re_tracer_frame.search(frame[0]):
        return True
    if _re_with_stan_frame.search(frame[2]):
        return True
    return False


def _apply_stack_limit(
    sanitized_stack: List[dict], limit: int, use_full_stack: bool
) -> List[dict]:
    """
    Apply frame limit to the sanitized stack.
    
    Args:
        sanitized_stack: List of stack frames
        limit: Maximum number of frames to include
        use_full_stack: If True, ignore the limit
    
    Returns:
        Limited stack trace
    """
    if use_full_stack or len(sanitized_stack) <= limit:
        return sanitized_stack
    # (limit * -1) gives us negative form of <limit> used for
    # slicing from the end of the list. e.g. stack[-25:]
    return sanitized_stack[(limit * -1) :]


def add_stack(
    level: str, limit: int, is_errored: bool = False
) -> Optional[List[dict]]:
    """
    Capture and return a stack trace based on configuration.
    
    This function collects the current call stack, filters out Instana
    internal frames, and applies the configured limit.
    
    Args:
        level: Stack trace collection level ("all", "error", or "none")
        limit: Maximum number of frames to include (1-40)
        is_errored: Whether the span has errors (ec > 0)
    
    Returns:
        List of stack frames in format [{"c": file, "n": line, "m": method}, ...]
        or None if stack trace should not be collected
    """
    try:
        # Determine if we should collect stack trace
        if not _should_collect_stack(level, is_errored):
            return None

        # For erroneous EXIT spans, MAY consider the whole stack
        use_full_stack = is_errored

        # Enforce hard limit of 40 frames (unless errored and using full stack)
        if not use_full_stack and limit > 40:
            limit = 40

        sanitized_stack = []
        trace_back = traceback.extract_stack()
        trace_back.reverse()

        for frame in trace_back:
            if _should_exclude_frame(frame):
                continue
            sanitized_stack.append({"c": frame[0], "n": frame[1], "m": frame[2]})

        # Apply limit (unless it's an errored span and we want full stack)
        return _apply_stack_limit(sanitized_stack, limit, use_full_stack)

    except Exception:
        logger.debug("add_stack: ", exc_info=True)
        return None


def add_stack_trace_if_needed(span: "InstanaSpan") -> None:
    """
    Add stack trace to span based on configuration before span ends.
    
    This function checks if the span is an EXIT span and if so, captures
    a stack trace based on the configured level and limit. It supports
    technology-specific configuration overrides via get_stack_trace_config().
    
    Args:
        span: The InstanaSpan to potentially add stack trace to
    """
    if span.name in EXIT_SPANS:
        # Get configuration from agent options (with technology-specific overrides)
        options = span._span_processor.agent.options
        level, limit = options.get_stack_trace_config(span.name)
        
        # Check if span is errored
        is_errored = span.attributes.get("ec", 0) > 0
        
        # Capture stack trace using add_stack function
        span.stack = add_stack(
            level=level,
            limit=limit,
            is_errored=is_errored
        )
