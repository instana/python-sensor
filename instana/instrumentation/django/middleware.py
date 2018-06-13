from __future__ import absolute_import
import opentracing as ot
import opentracing.ext.tags as ext
import wrapt
import sys
from ...log import logger
from ... import internal_tracer



DJ_INSTANA_MIDDLEWARE = 'instana.instrumentation.django.middleware.InstanaMiddleware'

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
        try:
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
        except Exception as e:
            logger.debug("Instana middleware @ process_response: ", e)

    def process_response(self, request, response):
        try:
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
        except Exception as e:
            logger.debug("Instana middleware @ process_response: ", e)
        finally:
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

        # Django >=1.10 to <2.0 support old-style MIDDLEWARE_CLASSES so we
        # do as well here
        if hasattr(settings, 'MIDDLEWARE'):
            if DJ_INSTANA_MIDDLEWARE in settings.MIDDLEWARE:
                return wrapped(*args, **kwargs)

            # Save the list of middleware for Snapshot reporting
            internal_tracer.sensor.meter.djmw = settings.MIDDLEWARE

            if type(settings.MIDDLEWARE) is tuple:
                settings.MIDDLEWARE = (DJ_INSTANA_MIDDLEWARE,) + settings.MIDDLEWARE
            elif type(settings.MIDDLEWARE) is list:
                settings.MIDDLEWARE = [DJ_INSTANA_MIDDLEWARE] + settings.MIDDLEWARE
            else:
                logger.warn("Instana: Couldn't add InstanaMiddleware to Django")

        elif hasattr(settings, 'MIDDLEWARE_CLASSES'):
            if DJ_INSTANA_MIDDLEWARE in settings.MIDDLEWARE_CLASSES:
                return wrapped(*args, **kwargs)

            # Save the list of middleware for Snapshot reporting
            internal_tracer.sensor.meter.djmw = settings.MIDDLEWARE_CLASSES

            if type(settings.MIDDLEWARE_CLASSES) is tuple:
                settings.MIDDLEWARE_CLASSES = (DJ_INSTANA_MIDDLEWARE,) + settings.MIDDLEWARE_CLASSES
            elif type(settings.MIDDLEWARE_CLASSES) is list:
                settings.MIDDLEWARE_CLASSES = [DJ_INSTANA_MIDDLEWARE] + settings.MIDDLEWARE_CLASSES
            else:
                logger.warn("Instana: Couldn't add InstanaMiddleware to Django")

        else:
            logger.warn("Instana: Couldn't find middleware settings")

        return wrapped(*args, **kwargs)
    except Exception as e:
            logger.warn("Instana: Couldn't add InstanaMiddleware to Django: ", e)

try:
    if 'django' in sys.modules:
        wrapt.wrap_function_wrapper('django.core.handlers.base', 'BaseHandler.load_middleware', load_middleware_wrapper)
except:
    pass
