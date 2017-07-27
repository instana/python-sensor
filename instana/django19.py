from __future__ import print_function
import opentracing as ot
from instana import tracer, options
import opentracing.ext.tags as ext


DJ19_INSTANA_MIDDLEWARE = 'instana.django19.InstanaMiddleware19'


class InstanaMiddleware19(object):
    """ Django 1.9 Middleware to provide request tracing for Instana """
    def __init__(self):
        opts = options.Options(service="Django")
        ot.global_tracer = tracer.InstanaTracer(opts)
        self.span = None
        self

    def process_request(self, request):
        env = request.environ
        if 'HTTP_X_INSTANA_T' in env and 'HTTP_X_INSTANA_S' in env:
            ctx = ot.global_tracer.extract(ot.Format.HTTP_HEADERS, env)
            span = ot.global_tracer.start_span("django", child_of=ctx)
        else:
            span = ot.global_tracer.start_span("django")

        span.set_tag(ext.HTTP_URL, env['PATH_INFO'])
        span.set_tag("http.params", env['QUERY_STRING'])
        span.set_tag(ext.HTTP_METHOD, request.method)
        span.set_tag("http.host", env['HTTP_HOST'])
        self.span = span

    def process_response(self, request, response):
        if self.span:
            self.span.set_tag(ext.HTTP_STATUS_CODE, response.status_code)
            ot.global_tracer.inject(self.span.context, ot.Format.HTTP_HEADERS, response)
            self.span.finish()
            self.span = None
        return response



def hook(module):
    """ Hook method to install the Instana middleware into Django """
    if DJ19_INSTANA_MIDDLEWARE in module.settings.MIDDLEWARE_CLASSES:
        return

    if type(module.settings.MIDDLEWARE_CLASSES) is tuple:
        module.settings.MIDDLEWARE_CLASSES = (DJ19_INSTANA_MIDDLEWARE,) + module.settings.MIDDLEWARE_CLASSES
    elif type(module.settings.MIDDLEWARE_CLASSES) is list:
        module.settings.MIDDLEWARE_CLASSES = [DJ19_INSTANA_MIDDLEWARE] + module.settings.MIDDLEWARE_CLASSES
    else:
        print("Instana: Couldn't add InstanaMiddleware to Django")
