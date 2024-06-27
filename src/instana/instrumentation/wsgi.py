# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instana WSGI Middleware
"""
from instana.propagators.format import Format
from opentelemetry.semconv.trace import SpanAttributes as tags

from ..singletons import agent, tracer
from ..util.secrets import strip_secrets_from_query


class InstanaWSGIMiddleware(object):
    """ Instana WSGI middleware """

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

            res = start_response(status, headers, exc_info)

            sc = status.split(' ')[0]
            if 500 <= int(sc):
                self.span.mark_as_errored()

            self.span.set_attribute(tags.HTTP_STATUS_CODE, sc)
            self.span.end()
            return res

        ctx = tracer.extract(Format.HTTP_HEADERS, env)
        self.span = tracer.start_span("wsgi", context=ctx)

        if agent.options.extra_http_headers is not None:
            for custom_header in agent.options.extra_http_headers:
                # Headers are available in this format: HTTP_X_CAPTURE_THIS
                wsgi_header = ('HTTP_' + custom_header.upper()).replace('-', '_')
                if wsgi_header in env:
                    self.span.set_attribute(
                        "http.header.%s" % custom_header, env[wsgi_header]
                    )

        if 'PATH_INFO' in env:
            self.span.set_attribute("http.path", env["PATH_INFO"])
        if 'QUERY_STRING' in env and len(env['QUERY_STRING']):
            scrubbed_params = strip_secrets_from_query(env['QUERY_STRING'], agent.options.secrets_matcher,
                                                       agent.options.secrets_list)
            self.span.set_attribute("http.params", scrubbed_params)
        if 'REQUEST_METHOD' in env:
            self.span.set_attribute(tags.HTTP_METHOD, env["REQUEST_METHOD"])
        if 'HTTP_HOST' in env:
            self.span.set_attribute("http.host", env["HTTP_HOST"])

        return self.app(environ, new_start_response)
