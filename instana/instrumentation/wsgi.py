"""
Instana WSGI Middleware
"""
import opentracing as ot
import opentracing.ext.tags as tags

from ..singletons import agent, tracer
from ..util import strip_secrets_from_query


class InstanaWSGIMiddleware(object):
    """ Instana WSGI middleware """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        env = environ

        def new_start_response(status, headers, exc_info=None):
            """Modified start response with additional headers."""
            tracer.inject(self.scope.span.context, ot.Format.HTTP_HEADERS, headers)
            headers.append(('Server-Timing', "intid;desc=%s" % self.scope.span.context.trace_id))

            res = start_response(status, headers, exc_info)

            sc = status.split(' ')[0]
            if 500 <= int(sc) <= 511:
                self.scope.span.mark_as_errored()

            self.scope.span.set_tag(tags.HTTP_STATUS_CODE, sc)
            self.scope.close()
            return res

        ctx = tracer.extract(ot.Format.HTTP_HEADERS, env)
        self.scope = tracer.start_active_span("wsgi", child_of=ctx)

        if agent.options.extra_http_headers is not None:
            for custom_header in agent.options.extra_http_headers:
                # Headers are available in this format: HTTP_X_CAPTURE_THIS
                wsgi_header = ('HTTP_' + custom_header.upper()).replace('-', '_')
                if wsgi_header in env:
                    self.scope.span.set_tag("http.%s" % custom_header, env[wsgi_header])

        if 'PATH_INFO' in env:
            self.scope.span.set_tag('http.path', env['PATH_INFO'])
        if 'QUERY_STRING' in env and len(env['QUERY_STRING']):
            scrubbed_params = strip_secrets_from_query(env['QUERY_STRING'], agent.options.secrets_matcher, agent.options.secrets_list)
            self.scope.span.set_tag("http.params", scrubbed_params)
        if 'REQUEST_METHOD' in env:
            self.scope.span.set_tag(tags.HTTP_METHOD, env['REQUEST_METHOD'])
        if 'HTTP_HOST' in env:
            self.scope.span.set_tag("http.host", env['HTTP_HOST'])

        return self.app(environ, new_start_response)
