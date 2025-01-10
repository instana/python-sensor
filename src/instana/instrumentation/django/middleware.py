# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

try:
    import sys

    from django import VERSION as django_version
    from opentelemetry import context, trace
    from opentelemetry.semconv.trace import SpanAttributes
    import wrapt
    from typing import TYPE_CHECKING, Dict, Any, Callable, Optional, List, Tuple, Type

    from instana.log import logger
    from instana.singletons import agent, tracer
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import extract_custom_headers
    from instana.propagators.format import Format

    if TYPE_CHECKING:
        from django.core.handlers.base import BaseHandler
        from django.http import HttpRequest, HttpResponse

    DJ_INSTANA_MIDDLEWARE = (
        "instana.instrumentation.django.middleware.InstanaMiddleware"
    )

    if django_version >= (2, 0):
        # Since Django 2.0, only `settings.MIDDLEWARE` is supported, so new-style
        # middlewares can be used.
        class MiddlewareMixin:
            def __init__(self, get_response):
                self.get_response = get_response

            def __call__(self, request):
                self.process_request(request)
                response = self.get_response(request)
                return self.process_response(request, response)

    else:
        # Note: For 1.11 <= django_version < 2.0
        # Django versions 1.x can use `settings.MIDDLEWARE_CLASSES` and expect
        # old-style middlewares, which are created by inheriting from
        # `deprecation.MiddlewareMixin` since its creation in Django 1.10 and 1.11
        from django.utils.deprecation import MiddlewareMixin

    class InstanaMiddleware(MiddlewareMixin):
        """Django Middleware to provide request tracing for Instana"""

        def __init__(
            self,
            get_response: Optional[Callable[["HttpRequest"], "HttpResponse"]] = None,
        ) -> None:
            super(InstanaMiddleware, self).__init__(get_response)
            self.get_response = get_response

        def process_request(self, request: Type["HttpRequest"]) -> None:
            try:
                env = request.META

                span_context = tracer.extract(Format.HTTP_HEADERS, env)

                span = tracer.start_span("django", span_context=span_context)
                request.span = span

                ctx = trace.set_span_in_context(span)
                token = context.attach(ctx)
                request.token = token

                extract_custom_headers(span, env, format=True)

                request.span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)
                if "PATH_INFO" in env:
                    request.span.set_attribute(
                        SpanAttributes.HTTP_URL, env["PATH_INFO"]
                    )
                if "QUERY_STRING" in env and len(env["QUERY_STRING"]):
                    scrubbed_params = strip_secrets_from_query(
                        env["QUERY_STRING"],
                        agent.options.secrets_matcher,
                        agent.options.secrets_list,
                    )
                    request.span.set_attribute("http.params", scrubbed_params)
                if "HTTP_HOST" in env:
                    request.span.set_attribute(SpanAttributes.HTTP_HOST, env["HTTP_HOST"])
            except Exception:
                logger.debug("Django middleware @ process_request", exc_info=True)

        def process_response(
            self, request: Type["HttpRequest"], response: "HttpResponse"
        ) -> "HttpResponse":
            try:
                if request.span:
                    if 500 <= response.status_code:
                        request.span.assure_errored()
                    # for django >= 2.2
                    if request.resolver_match is not None and hasattr(
                        request.resolver_match, "route"
                    ):
                        path_tpl = request.resolver_match.route
                    # django < 2.2 or in case of 404
                    else:
                        try:
                            from django.urls import resolve

                            view_name = resolve(request.path)._func_path
                            path_tpl = "".join(url_pattern_route(view_name))
                        except Exception:
                            # the resolve method can fire a Resolver404 exception, in this case there is no matching route
                            # so the path_tpl is set to None in order not to be added as a tag
                            path_tpl = None
                    if path_tpl:
                        request.span.set_attribute("http.path_tpl", path_tpl)

                    request.span.set_attribute(
                        SpanAttributes.HTTP_STATUS_CODE, response.status_code
                    )
                    if hasattr(response, "headers"):
                        extract_custom_headers(
                            request.span, response.headers, format=False
                        )
                    tracer.inject(request.span.context, Format.HTTP_HEADERS, response)
            except Exception:
                logger.debug("Instana middleware @ process_response", exc_info=True)
            finally:
                if hasattr(request, "span") and request.span:
                    if request.span.is_recording():
                        request.span.end()
                    request.span = None
                if hasattr(request, "token") and request.token:
                    context.detach(request.token)
                    request.token = None
            return response

        def process_exception(
            self, request: Type["HttpRequest"], exception: Exception
        ) -> None:
            from django.http.response import Http404

            if isinstance(exception, Http404):
                return None

            if request.span:
                request.span.record_exception(exception)

    def url_pattern_route(view_name: str) -> Callable[..., object]:
        from django.conf import settings

        try:
            from django.urls import (
                RegexURLPattern as URLPattern,
                RegexURLResolver as URLResolver,
            )
        except ImportError:
            from django.urls import URLPattern, URLResolver

        urlconf = __import__(settings.ROOT_URLCONF, {}, {}, [""])

        def list_urls(
            urlpatterns: List[str], parent_pattern: Optional[List[str]] = None
        ) -> Callable[..., object]:
            if not urlpatterns:
                return
            if parent_pattern is None:
                parent_pattern = []
            first = urlpatterns[0]
            if isinstance(first, URLPattern):
                if first.lookup_str == view_name:
                    if hasattr(first, "regex"):
                        return parent_pattern + [str(first.regex.pattern)]
                    else:
                        return parent_pattern + [str(first.pattern)]
            elif isinstance(first, URLResolver):
                if hasattr(first, "regex"):
                    return list_urls(
                        first.url_patterns, parent_pattern + [str(first.regex.pattern)]
                    )
                else:
                    return list_urls(
                        first.url_patterns, parent_pattern + [str(first.pattern)]
                    )
            return list_urls(urlpatterns[1:], parent_pattern)

        return list_urls(urlconf.urlpatterns)

    def load_middleware_wrapper(
        wrapped: Callable[..., None],
        instance: Type["BaseHandler"],
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> Callable[..., None]:
        try:
            from django.conf import settings

            # Django >=1.10 to <2.0 support old-style MIDDLEWARE_CLASSES so we
            # do as well here
            if hasattr(settings, "MIDDLEWARE") and settings.MIDDLEWARE is not None:
                if DJ_INSTANA_MIDDLEWARE in settings.MIDDLEWARE:
                    return wrapped(*args, **kwargs)

                if isinstance(settings.MIDDLEWARE, tuple):
                    settings.MIDDLEWARE = (DJ_INSTANA_MIDDLEWARE,) + settings.MIDDLEWARE
                elif isinstance(settings.MIDDLEWARE, list):
                    settings.MIDDLEWARE = [DJ_INSTANA_MIDDLEWARE] + settings.MIDDLEWARE
                else:
                    logger.warning("Instana: Couldn't add InstanaMiddleware to Django")

            elif (
                hasattr(settings, "MIDDLEWARE_CLASSES")
                and settings.MIDDLEWARE_CLASSES is not None
            ):  # pragma: no cover
                if DJ_INSTANA_MIDDLEWARE in settings.MIDDLEWARE_CLASSES:
                    return wrapped(*args, **kwargs)

                if isinstance(settings.MIDDLEWARE_CLASSES, tuple):
                    settings.MIDDLEWARE_CLASSES = (
                        DJ_INSTANA_MIDDLEWARE,
                    ) + settings.MIDDLEWARE_CLASSES
                elif isinstance(settings.MIDDLEWARE_CLASSES, list):
                    settings.MIDDLEWARE_CLASSES = [
                        DJ_INSTANA_MIDDLEWARE
                    ] + settings.MIDDLEWARE_CLASSES
                else:
                    logger.warning("Instana: Couldn't add InstanaMiddleware to Django")

            else:  # pragma: no cover
                logger.warning("Instana: Couldn't find middleware settings")

            return wrapped(*args, **kwargs)
        except Exception:
            logger.warning(
                "Instana: Couldn't add InstanaMiddleware to Django: ", exc_info=True
            )

    try:
        logger.debug("Instrumenting django")
        wrapt.wrap_function_wrapper(
            "django.core.handlers.base",
            "BaseHandler.load_middleware",
            load_middleware_wrapper,
        )

        if "/tmp/.instana/python" in sys.path:  # pragma: no cover
            # If we are instrumenting via AutoTrace (in an already running process), then the
            # WSGI middleware has to be live reloaded.
            from django.core.servers.basehttp import get_internal_wsgi_application
            from django.core.exceptions import ImproperlyConfigured

            try:
                wsgiapp = get_internal_wsgi_application()
                wsgiapp.load_middleware()
            except ImproperlyConfigured:
                pass

    except Exception:
        logger.debug("django.middleware:", exc_info=True)

except ImportError:
    pass
