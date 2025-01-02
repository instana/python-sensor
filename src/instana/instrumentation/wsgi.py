# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instana WSGI Middleware
"""

from typing import Dict, Any, Callable, List, Tuple, Optional, TYPE_CHECKING

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry import context, trace

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent, tracer
from instana.util.secrets import strip_secrets_from_query

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan


class InstanaWSGIMiddleware(object):
    """Instana WSGI middleware"""

    def __init__(self, app: object) -> None:
        self.app = app

    def _extract_custom_headers(
        self, span: "InstanaSpan", headers: List[Tuple[object, ...]], type
    ) -> None:
        if not agent.options.extra_http_headers or not headers:
            return
        try:
            for custom_header in agent.options.extra_http_headers:
                if type == "request" and isinstance(headers, dict):
                    # Headers are available in this format: HTTP_X_CAPTURE_THIS
                    wsgi_header = ("HTTP_" + custom_header.upper()).replace("-", "_")
                    if wsgi_header in headers:
                        self.span.set_attribute(
                            f"http.header.{custom_header}", headers[wsgi_header]
                        )
                if type == "response" and isinstance(headers, list):
                    for header_pair in headers:
                        if header_pair[0].lower() == custom_header.lower():
                            span.set_attribute(
                                f"http.header.{custom_header}", header_pair[1],
                            )
        except Exception:
            logger.debug("extract_custom_headers: ", exc_info=True)

    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> object:
        env = environ

        def new_start_response(
            status: str,
            headers: List[Tuple[object, ...]],
            exc_info: Optional[Exception] = None,
        ) -> object:
            """Modified start response with additional headers."""
            self._extract_custom_headers(self.span, headers, type="response")

            tracer.inject(self.span.context, Format.HTTP_HEADERS, headers)

            headers_str = [
                (header[0], str(header[1]))
                if not isinstance(header[1], str)
                else header
                for header in headers
            ]
            res = start_response(status, headers_str, exc_info)

            sc = status.split(" ")[0]
            if 500 <= int(sc):
                self.span.mark_as_errored()

            self.span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, sc)
            if self.span and self.span.is_recording():
                self.span.end()
            if self.token:
                context.detach(self.token)
            return res

        span_context = tracer.extract(Format.HTTP_HEADERS, env)
        self.span = tracer.start_span("wsgi", span_context=span_context)

        ctx = trace.set_span_in_context(self.span)
        self.token = context.attach(ctx)

        self._extract_custom_headers(self.span, env, type="request")

        if "PATH_INFO" in env:
            self.span.set_attribute("http.path", env["PATH_INFO"])
        if "QUERY_STRING" in env and len(env["QUERY_STRING"]):
            scrubbed_params = strip_secrets_from_query(
                env["QUERY_STRING"],
                agent.options.secrets_matcher,
                agent.options.secrets_list,
            )
            self.span.set_attribute("http.params", scrubbed_params)
        if "REQUEST_METHOD" in env:
            self.span.set_attribute(SpanAttributes.HTTP_METHOD, env["REQUEST_METHOD"])
        if "HTTP_HOST" in env:
            self.span.set_attribute("http.host", env["HTTP_HOST"])

        return self.app(environ, new_start_response)
