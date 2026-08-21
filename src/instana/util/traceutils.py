# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


from collections.abc import Iterable
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Union,
)

from instana.log import logger
from instana.singletons import agent, get_tracer
from instana.span.span import InstanaSpan, get_current_span

if TYPE_CHECKING:
    from instana.tracer import InstanaTracer


def extract_custom_headers(
    span: "InstanaSpan",
    headers: Optional[Union[dict[str, Any], list[tuple[object, ...]], Iterable]] = None,
    format: Optional[bool] = False,
) -> None:
    if not (agent.options.extra_http_headers and headers):
        return
    try:
        for custom_header in agent.options.extra_http_headers:
            # Headers are available in the following formats: HTTP_X_CAPTURE_THIS, b'x-header-1', X-Capture-That
            expected_header = (
                ("HTTP_" + custom_header.upper()).replace("-", "_")
                if format
                else custom_header
            )
            for header in headers:
                if isinstance(header, tuple):
                    header_key = (
                        header[0].decode("utf-8")
                        if isinstance(header[0], bytes)
                        else header[0]
                    )
                    header_val = (
                        header[1].decode("utf-8")
                        if isinstance(header[1], bytes)
                        else header[1]
                    )
                    if header_key.lower() == expected_header.lower():
                        span.set_attribute(
                            f"http.header.{custom_header}",
                            header_val,
                        )
                elif header.lower() == expected_header.lower():
                    span.set_attribute(
                        f"http.header.{custom_header}", headers[expected_header]
                    )
    except Exception:
        logger.debug("extract_custom_headers: ", exc_info=True)


def get_tracer_tuple() -> tuple[
    Optional["InstanaTracer"],
    Optional["InstanaSpan"],
    Optional[str],
]:
    """Get a tuple of (tracer, span, span_name) for the current context.

    Returns a 3-tuple of (tracer, span, span_name). Returns (None, None, None)
    when no active recording span is found and allow_exit_as_root is False.
    """
    try:
        active_tracer = get_tracer()
        current_span = get_current_span()
        if current_span and isinstance(current_span, InstanaSpan):
            # asyncio Spans are used as NonRecording Spans solely for context propagation
            if current_span.is_recording() or current_span.name == "asyncio":
                return (active_tracer, current_span, current_span.name)
        elif current_span and current_span.is_recording():
            # A non-Instana recording span is active (e.g. OTel span from a third-party
            # library like LiteLLM/OpenAI SDK). Treat it as a valid parent context so
            # that exit spans (httpx, etc.) are still created and attached.
            return (active_tracer, None, None)
        if agent.options.allow_exit_as_root:
            return (active_tracer, None, None)
        return (None, None, None)
    except Exception:
        # Do not try to log this with instana, as there is no active tracer and there will be an infinite loop at least
        # for PY2
        return (None, None, None)
