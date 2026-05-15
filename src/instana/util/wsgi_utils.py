# (C) Copyright IBM Corp. 2026

"""
Shared WSGI Instrumentation Utilities

This module provides common utilities for WSGI instrumentation used by
both werkzeug.py and wsgi.py modules to avoid code duplication.
"""

from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional

from opentelemetry import context, trace
from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent, get_tracer
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import extract_custom_headers

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan


def create_span_with_context(environ: dict[str, Any]) -> tuple["InstanaSpan", Any]:
    """
    Create and configure a span with context for the request.

    Args:
        environ: WSGI environment dictionary

    Returns:
        Tuple of (span, context_token)
    """
    tracer = get_tracer()
    parent_context = tracer.extract(Format.HTTP_HEADERS, environ)
    span = tracer.start_span("wsgi", context=parent_context)

    ctx = trace.set_span_in_context(span)
    token = context.attach(ctx)

    extract_custom_headers(span, environ, format=True)
    set_request_attributes(span, environ)

    return span, token


def build_start_response(
    span: "InstanaSpan",
    start_response: Callable,
    status_as_string: bool = False,
) -> Callable:
    """
    Create an instrumented start_response callable.

    Args:
        span: The active span
        start_response: Original WSGI start_response callable
        status_as_string: If True, set status code as string (for wsgi.py compatibility)

    Returns:
        Wrapped start_response callable
    """

    def new_start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info: Optional[tuple[Any, Any, Any]] = None,
    ) -> Callable:
        """Modified start_response with trace context injection."""
        try:
            extract_custom_headers(span, headers)
            tracer = get_tracer()
            tracer.inject(
                span.context,
                Format.HTTP_HEADERS,
                headers,
            )

            status_code = parse_status_code(status)
            if status_code is not None:
                span.set_attribute(
                    SpanAttributes.HTTP_STATUS_CODE,
                    str(status_code) if status_as_string else status_code,
                )
                if status_code >= 500:
                    span.mark_as_errored()

            return start_response(
                status,
                normalize_headers(headers),
                exc_info,
            )
        except Exception:
            logger.debug("Error in WSGI start_response wrapper", exc_info=True)
            return start_response(status, headers, exc_info)

    return new_start_response


def normalize_headers(
    headers: list[tuple[str, Any]],
) -> list[tuple[str, str]]:
    """
    Ensure all header values are strings for WSGI compliance.

    Args:
        headers: List of (name, value) tuples

    Returns:
        List of (name, str_value) tuples
    """
    return [
        (name, value if isinstance(value, str) else str(value))
        for name, value in headers
    ]


def parse_status_code(status: str) -> Optional[int]:
    """
    Safely parse the HTTP status code from a WSGI status string.

    Args:
        status: WSGI status string (e.g., "200 OK")

    Returns:
        Status code as integer, or None if parsing fails
    """
    try:
        return int(status.split()[0])
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


def end_span_after_iterating(
    iterable: Iterable[bytes],
    span: "InstanaSpan",
    token: Any,
) -> Iterable[bytes]:
    """
    Generator that yields from the iterable and ensures span cleanup.

    Args:
        iterable: The response iterable from the application
        span: The active span
        token: The context token

    Yields:
        Response chunks from the iterable
    """
    try:
        yield from iterable
    finally:
        # Ensure iterable cleanup (important for generators)
        if hasattr(iterable, "close"):
            try:
                iterable.close()  # type: ignore
            except Exception:
                logger.debug("Error closing iterable", exc_info=True)

        # End span and detach token after iteration completes
        if span and span.is_recording():
            span.end()
        if token:
            context.detach(token)  # type: ignore


def scrub_query_params(query_string: str) -> Optional[str]:
    """
    Scrub secrets from query string parameters.

    Args:
        query_string: The query string to scrub

    Returns:
        Scrubbed query string if agent is available, otherwise returns
        the original query_string for debugging purposes
    """
    if agent is not None:
        return strip_secrets_from_query(
            query_string,
            agent.options.secrets_matcher,  # type: ignore
            agent.options.secrets_list,  # type: ignore
        )
    return query_string


def set_request_attributes(span: "InstanaSpan", environ: dict[str, Any]) -> None:
    """
    Extract and set HTTP attributes from the WSGI environ.

    Args:
        span: The active span
        environ: WSGI environment dictionary
    """
    try:
        # Set HTTP method
        if "REQUEST_METHOD" in environ:
            span.set_attribute(SpanAttributes.HTTP_METHOD, environ["REQUEST_METHOD"])

        # Set HTTP path
        if "PATH_INFO" in environ:
            span.set_attribute("http.path", environ["PATH_INFO"])

        # Set HTTP query parameters (with secrets scrubbed)
        if environ.get("QUERY_STRING", "").strip():
            scrubbed_params = scrub_query_params(environ["QUERY_STRING"])
            if scrubbed_params is not None:
                span.set_attribute("http.params", scrubbed_params)

        # Set HTTP host
        if "HTTP_HOST" in environ:
            span.set_attribute(
                SpanAttributes.HTTP_HOST,
                environ["HTTP_HOST"],
            )

        # Set HTTP URL (without query string to avoid exposing secrets)
        if "wsgi.url_scheme" in environ:
            scheme = environ["wsgi.url_scheme"]
            host = environ.get("HTTP_HOST", "")
            script_name = environ.get("SCRIPT_NAME", "")
            path = environ.get("PATH_INFO", "")

            url = f"{scheme}://{host}{script_name}{path}"
            span.set_attribute(SpanAttributes.HTTP_URL, url)

    except Exception:
        logger.debug("Error setting request attributes", exc_info=True)


# Made with Bob
