# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instana WSGI Middleware
"""

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry import context, trace

from instana.propagators.format import Format
from instana.singletons import agent, tracer
from instana.util.secrets import strip_secrets_from_query


class InstanaWSGIMiddleware(object):
    """Instana WSGI middleware"""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        env = environ

        def new_start_response(status, headers, exc_info=None):
            """Modified start response with additional headers."""
            tracer.inject(self.span.context, Format.HTTP_HEADERS, headers)
            headers.append(
                ("Server-Timing", "intid;desc=%s" % self.span.context.trace_id)
            )

            headers_str = [(header[0], str(header[1])) if not isinstance(header[1], str) else header for header in headers]
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

        if agent.options.extra_http_headers is not None:
            for custom_header in agent.options.extra_http_headers:
                # Headers are available in this format: HTTP_X_CAPTURE_THIS
                wsgi_header = ("HTTP_" + custom_header.upper()).replace("-", "_")
                if wsgi_header in env:
                    self.span.set_attribute(
                        "http.header.%s" % custom_header, env[wsgi_header]
                    )

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
