from __future__ import print_function
import opentracing as ot
from instana import internal_tracer
from instana.log import logger
import opentracing.ext.tags as ext
import wrapt
import os


DJ_INSTANA_MIDDLEWARE = 'instana.django.InstanaMiddleware'

try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object


class InstanaMiddleware(MiddlewareMixin):
    """ Django Middleware to provide request tracing for Instana """
    def __init__(self, get_response=None):
        self.get_response = get_response
        self

    def process_request(self, request):
        env = request.environ
        if 'HTTP_X_INSTANA_T' in env and 'HTTP_X_INSTANA_S' in env:
            ctx = internal_tracer.extract(ot.Format.HTTP_HEADERS, env)
            span = internal_tracer.start_span("django", child_of=ctx)
        else:
            span = internal_tracer.start_span("django")

        span.set_tag(ext.HTTP_URL, env['PATH_INFO'])
        span.set_tag("http.params", env['QUERY_STRING'])
        span.set_tag(ext.HTTP_METHOD, request.method)
        span.set_tag("http.host", env['HTTP_HOST'])
        self.span = span

    def process_response(self, request, response):
        if self.span:
            if 500 <= response.status_code <= 511:
                self.span.set_tag("error", True)
                ec = self.span.tags.get('ec', 0)
                if ec is 0:
                    self.span.set_tag("ec", ec+1)

            self.span.set_tag(ext.HTTP_STATUS_CODE, response.status_code)
            internal_tracer.inject(self.span.context, ot.Format.HTTP_HEADERS, response)
            self.span.finish()
            self.span = None
        return response

    def process_exception(self, request, exception):
        if self.span:
            self.span.log_kv({'message': exception})
            self.span.set_tag("error", True)
            ec = self.span.tags.get('ec', 0)
            self.span.set_tag("ec", ec+1)

def load_middleware_wrapper(wrapped, instance, args, kwargs):
    try:
        from django.conf import settings

        if DJ_INSTANA_MIDDLEWARE in settings.MIDDLEWARE:
            return

        if type(settings.MIDDLEWARE) is tuple:
            settings.MIDDLEWARE = (DJ_INSTANA_MIDDLEWARE,) + settings.MIDDLEWARE
        elif type(settings.MIDDLEWARE) is list:
            settings.MIDDLEWARE = [DJ_INSTANA_MIDDLEWARE] + settings.MIDDLEWARE
        else:
            logger.warn("Instana: Couldn't add InstanaMiddleware to Django")

        return wrapped(*args, **kwargs)

    except Exception as e:
            logger.warn("Instana: Couldn't add InstanaMiddleware to Django: ", e)

def hook(module):
    """ Hook method to install the Instana middleware into Django >= 1.10 """
    if "INSTANA_DEV" in os.environ:
        print("==============================================================")
        print("Instana: Running django hook")
        print("==============================================================")
    wrapt.wrap_function_wrapper(module, 'BaseHandler.load_middleware', load_middleware_wrapper)


def hook19(module):
    try:
        """ Hook method to install the Instana middleware into Django <= 1.9 """
        if "INSTANA_DEV" in os.environ:
            print("==============================================================")
            print("Instana: Running django19 hook")
            print("==============================================================")

        if DJ_INSTANA_MIDDLEWARE in module.settings.MIDDLEWARE_CLASSES:
            return

        if type(module.settings.MIDDLEWARE_CLASSES) is tuple:
            module.settings.MIDDLEWARE_CLASSES = (DJ_INSTANA_MIDDLEWARE,) + module.settings.MIDDLEWARE_CLASSES
        elif type(module.settings.MIDDLEWARE_CLASSES) is list:
            module.settings.MIDDLEWARE_CLASSES = [DJ_INSTANA_MIDDLEWARE] + module.settings.MIDDLEWARE_CLASSES
        else:
            logger.warn("Instana: Couldn't add InstanaMiddleware to Django")

    except Exception as e:
            logger.warn("Instana: Couldn't add InstanaMiddleware to Django: ", e)
