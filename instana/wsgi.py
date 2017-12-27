import opentracing as ot
from instana import internal_tracer
import opentracing.ext.tags as tags


class iWSGIMiddleware(object):
    """ Instana WSGI middleware """

    def __init__(self, app):
        self.app = app
        self

    def __call__(self, environ, start_response):
        env = environ

        def new_start_response(status, headers, exc_info=None):
            """Modified start response with additional headers."""
            internal_tracer.inject(span.context, ot.Format.HTTP_HEADERS, headers)
            res = start_response(status, headers, exc_info)

            sc = status.split(' ')[0]
            if 500 <= int(sc) <= 511:
                span.set_tag("error", True)
                ec = span.tags.get('ec', 0)
                span.set_tag("ec", ec+1)

            span.set_tag(tags.HTTP_STATUS_CODE, sc)
            span.finish()
            return res

        if 'HTTP_X_INSTANA_T' in env and 'HTTP_X_INSTANA_S' in env:
            ctx = internal_tracer.extract(ot.Format.HTTP_HEADERS, env)
            span = internal_tracer.start_span("wsgi", child_of=ctx)
        else:
            span = internal_tracer.start_span("wsgi")

        span.set_tag(tags.HTTP_URL, env['PATH_INFO'])
        span.set_tag("http.params", env['QUERY_STRING'])
        span.set_tag(tags.HTTP_METHOD, env['REQUEST_METHOD'])
        span.set_tag("http.host", env['HTTP_HOST'])

        return self.app(environ, new_start_response)


def make_middleware(app=None, *args, **kw):
    """ Given an app, return that app wrapped in iWSGIMiddleware """
    app = iWSGIMiddleware(app, *args, **kw)
    return app
