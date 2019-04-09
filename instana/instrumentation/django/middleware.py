from __future__ import absolute_import

import sys

import opentracing as ot
import opentracing.ext.tags as ext
import wrapt

from ...log import logger
from ...singletons import agent, tracer
from ...util import strip_secrets

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

            ctx = tracer.extract(ot.Format.HTTP_HEADERS, env)
            request.iscope = tracer.start_active_span('django', child_of=ctx)

            if agent.extra_headers is not None:
                for custom_header in agent.extra_headers:
                    # Headers are available in this format: HTTP_X_CAPTURE_THIS
                    django_header = ('HTTP_' + custom_header.upper()).replace('-', '_')
                    if django_header in env:
                        request.iscope.span.set_tag("http.%s" % custom_header, env[django_header])

            request.iscope.span.set_tag(ext.HTTP_METHOD, request.method)
            if 'PATH_INFO' in env:
                request.iscope.span.set_tag(ext.HTTP_URL, env['PATH_INFO'])
            if 'QUERY_STRING' in env and len(env['QUERY_STRING']):
                scrubbed_params = strip_secrets(env['QUERY_STRING'], agent.secrets_matcher, agent.secrets_list)
                request.iscope.span.set_tag("http.params", scrubbed_params)
            if 'HTTP_HOST' in env:
                request.iscope.span.set_tag("http.host", env['HTTP_HOST'])
        except Exception:
            logger.debug("Django middleware @ process_request", exc_info=True)

    def process_response(self, request, response):
        try:
            if request.iscope is not None:
                if 500 <= response.status_code <= 511:
                    request.iscope.span.set_tag("error", True)
                    ec = request.iscope.span.tags.get('ec', 0)
                    if ec is 0:
                        request.iscope.span.set_tag("ec", ec+1)

                request.iscope.span.set_tag(ext.HTTP_STATUS_CODE, response.status_code)
                tracer.inject(request.iscope.span.context, ot.Format.HTTP_HEADERS, response)
                response['Server-Timing'] = "intid;desc=%s" % request.iscope.span.context.trace_id

        except Exception:
            logger.debug("Instana middleware @ process_response", exc_info=True)
        finally:
            if request.iscope is not None:
                request.iscope.close()
                request.iscope = None
            return response

    def process_exception(self, request, exception):
        if request.iscope is not None:
            request.iscope.span.set_tag(ext.HTTP_STATUS_CODE, 500)
            request.iscope.span.set_tag('http.error', str(exception))
            request.iscope.span.set_tag("error", True)
            ec = request.iscope.span.tags.get('ec', 0)
            request.iscope.span.set_tag("ec", ec+1)


def load_middleware_wrapper(wrapped, instance, args, kwargs):
    try:
        from django.conf import settings

        # Django >=1.10 to <2.0 support old-style MIDDLEWARE_CLASSES so we
        # do as well here
        if hasattr(settings, 'MIDDLEWARE') and settings.MIDDLEWARE is not None:
            if DJ_INSTANA_MIDDLEWARE in settings.MIDDLEWARE:
                return wrapped(*args, **kwargs)

            # Save the list of middleware for Snapshot reporting
            agent.sensor.meter.djmw = settings.MIDDLEWARE

            if type(settings.MIDDLEWARE) is tuple:
                settings.MIDDLEWARE = (DJ_INSTANA_MIDDLEWARE,) + settings.MIDDLEWARE
            elif type(settings.MIDDLEWARE) is list:
                settings.MIDDLEWARE = [DJ_INSTANA_MIDDLEWARE] + settings.MIDDLEWARE
            else:
                logger.warn("Instana: Couldn't add InstanaMiddleware to Django")

        elif hasattr(settings, 'MIDDLEWARE_CLASSES') and settings.MIDDLEWARE_CLASSES is not None:
            if DJ_INSTANA_MIDDLEWARE in settings.MIDDLEWARE_CLASSES:
                return wrapped(*args, **kwargs)

            # Save the list of middleware for Snapshot reporting
            agent.sensor.meter.djmw = settings.MIDDLEWARE_CLASSES

            if type(settings.MIDDLEWARE_CLASSES) is tuple:
                settings.MIDDLEWARE_CLASSES = (DJ_INSTANA_MIDDLEWARE,) + settings.MIDDLEWARE_CLASSES
            elif type(settings.MIDDLEWARE_CLASSES) is list:
                settings.MIDDLEWARE_CLASSES = [DJ_INSTANA_MIDDLEWARE] + settings.MIDDLEWARE_CLASSES
            else:
                logger.warn("Instana: Couldn't add InstanaMiddleware to Django")

        else:
            logger.warn("Instana: Couldn't find middleware settings")

        return wrapped(*args, **kwargs)
    except Exception:
            logger.warn("Instana: Couldn't add InstanaMiddleware to Django: ", exc_info=True)


try:
    if 'django' in sys.modules:
        logger.debug("Instrumenting django")
        wrapt.wrap_function_wrapper('django.core.handlers.base', 'BaseHandler.load_middleware', load_middleware_wrapper)
except Exception:
    pass
