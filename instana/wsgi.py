import opentracing as ot
from instana import tracer, options
import opentracing.ext.tags as ext
import logging


class iWSGIMiddleware(object):
    """ Instana WSGI middleware """

    def __init__(self, app):
        self.app = app
        opts = options.Options(log_level=logging.DEBUG)
        ot.global_tracer = tracer.InstanaTracer(opts)
        self

    def __call__(self, environ, start_response):
        env = environ

        def new_start_response(status, headers, exc_info=None):
            """Modified start response with additional headers."""
            ot.global_tracer.inject(span.context, ot.Format.HTTP_HEADERS, headers)
            res = start_response(status, headers, exc_info)
            span.set_tag(ext.HTTP_STATUS_CODE, status.split(' ')[0])
            span.finish()
            return res

        if 'HTTP_X_INSTANA_T' in env and 'HTTP_X_INSTANA_S' in env:
            ctx = ot.global_tracer.extract(ot.Format.HTTP_HEADERS, env)
            span = ot.global_tracer.start_span("wsgi", child_of=ctx)
        else:
            span = ot.global_tracer.start_span("wsgi")

        span.set_tag(ext.HTTP_URL, env['PATH_INFO'])
        span.set_tag("http.params", env['QUERY_STRING'])
        span.set_tag(ext.HTTP_METHOD, env['REQUEST_METHOD'])
        span.set_tag("http.host", env['HTTP_HOST'])

        return self.app(environ, new_start_response)


def make_middleware(app=None, *args, **kw):
    """ Given an app, return that app wrapped in iWSGIMiddleware """
    app = iWSGIMiddleware(app, *args, **kw)
    return app
