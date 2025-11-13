# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instana WSGI Middleware
"""

from typing import Dict, Any, Callable, List, Tuple, Optional, Iterable, TYPE_CHECKING

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry import context, trace

from instana.propagators.format import Format
from instana.singletons import agent, tracer
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import extract_custom_headers

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan

class InstanaWSGIMiddleware(object):
    """Instana WSGI middleware"""

    def __init__(self, app: object) -> None:
        self.app = app

    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> object:
        env = environ

        # Extract context and start span
        span_context = tracer.extract(Format.HTTP_HEADERS, env)
        span = tracer.start_span("wsgi", span_context=span_context)

        # Attach context - this makes the span current
        ctx = trace.set_span_in_context(span)
        token = context.attach(ctx)

        # Extract custom headers from request
        extract_custom_headers(span, env, format=True)

        # Set request attributes
        _set_request_attributes(span, env)

        def new_start_response(
            status: str,
            headers: List[Tuple[object, ...]],
            exc_info: Optional[Exception] = None,
        ) -> object:
            """Modified start response with additional headers."""
            extract_custom_headers(span, headers)

            tracer.inject(span.context, Format.HTTP_HEADERS, headers)

            headers_str = [
                (header[0], str(header[1]))
                if not isinstance(header[1], str)
                else header
                for header in headers
            ]

            # Set status code attribute
            sc = status.split(" ")[0]
            if 500 <= int(sc):
                span.mark_as_errored()

            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, sc)

            return start_response(status, headers_str, exc_info)

        try:
            iterable = self.app(environ, new_start_response)

            # Wrap the iterable to ensure span ends after iteration completes
            return _end_span_after_iterating(iterable, span, token)

        except Exception as exc:
            # If exception occurs before iteration completes, end span and detach token
            if span and span.is_recording():
                span.record_exception(exc)
                span.end()
            if token:
                context.detach(token)
            raise exc


def _end_span_after_iterating(
    iterable: Iterable[object], span: "InstanaSpan", token: object
) -> Iterable[object]:
    try:
        yield from iterable
    finally:
        # Ensure iterable cleanup (important for generators)
        if hasattr(iterable, "close"):
            iterable.close()

        # End span and detach token after iteration completes
        if span and span.is_recording():
            span.end()
        if token:
            context.detach(token)

def _set_request_attributes(span: "InstanaSpan", env: Dict[str, Any]) -> None:
    if "PATH_INFO" in env:
        span.set_attribute("http.path", env["PATH_INFO"])
    if "QUERY_STRING" in env and len(env["QUERY_STRING"]):
        scrubbed_params = strip_secrets_from_query(
            env["QUERY_STRING"],
            agent.options.secrets_matcher,
            agent.options.secrets_list,
        )
        span.set_attribute("http.params", scrubbed_params)
    if "REQUEST_METHOD" in env:
        span.set_attribute(SpanAttributes.HTTP_METHOD, env["REQUEST_METHOD"])
    if "HTTP_HOST" in env:
        span.set_attribute(SpanAttributes.HTTP_HOST, env["HTTP_HOST"])
