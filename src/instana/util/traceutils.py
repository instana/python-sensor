# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from typing import (
    Optional,
    Tuple,
    TYPE_CHECKING,
    Union,
    Dict,
    List,
    Any,
    Iterable,
)

from instana.log import logger
from instana.singletons import agent, tracer
from instana.span.span import get_current_span

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan
    from instana.tracer import InstanaTracer


def extract_custom_headers(
    span: "InstanaSpan",
    headers: Optional[Union[Dict[str, Any], List[Tuple[object, ...]], Iterable]] = None,
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


def get_active_tracer() -> Optional["InstanaTracer"]:
    """Get the currently active tracer if one exists."""
    try:
        current_span = get_current_span()
        if current_span:
            # asyncio Spans are used as NonRecording Spans solely for context propagation
            if current_span.is_recording() or current_span.name == "asyncio":
                return tracer
            return None
        return None
    except Exception:
        # Do not try to log this with instana, as there is no active tracer and there will be an infinite loop at least
        # for PY2
        return None


def get_tracer_tuple() -> (
    Tuple[
        Optional["InstanaTracer"],
        Optional["InstanaSpan"],
        Optional[str],
    ]
):
    """Get a tuple of (tracer, span, span_name) for the current context."""
    active_tracer = get_active_tracer()
    current_span = get_current_span()
    if active_tracer:
        return (active_tracer, current_span, current_span.name)
    elif agent.options.allow_exit_as_root:
        return (tracer, None, None)
    return (None, None, None)


def tracing_is_off() -> bool:
    """Check if tracing is currently disabled."""
    return not (bool(get_active_tracer()) or agent.options.allow_exit_as_root)
