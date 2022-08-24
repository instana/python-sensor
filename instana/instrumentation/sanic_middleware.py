
import opentracing
from ..log import logger
from ..singletons import async_tracer, agent
from ..util.secrets import strip_secrets_from_query
from ..util.traceutils import extract_custom_headers

class InstanaSanicMiddleware:
    def __init__( self, app):
        @app.on_request
        def request_with_instana(request):
            """Function starts tracing requests with Instana
            Args:
                request: Sanic HttpRequest Object
            """
            logger.debug("Instana instrumenting sanic request")
            if not ("http" in request.scheme or "ws" in request.scheme):
                return
            ctx = async_tracer.extract(opentracing.Format.HTTP_HEADERS, request.headers)
            with async_tracer.start_active_span("asgi", child_of=ctx) as scope:
                scope.span.set_tag('span.kind', 'entry')
                scope.span.set_tag('http.path', request.path)
                scope.span.set_tag('http.method', request.method)
                scope.span.set_tag('http.host', request.host)
                if hasattr(request, "url"):
                    scope.span.set_tag("http.url", request.url)

                query = request.query_string

                if isinstance(query, (str, bytes)) and len(query):
                    if isinstance(query, bytes):
                        query = query.decode('utf-8')
                    scrubbed_params = strip_secrets_from_query(query, agent.options.secrets_matcher,
                                                               agent.options.secrets_list)
                    scope.span.set_tag("http.params", scrubbed_params)

                if agent.options.extra_http_headers is not None:
                    extract_custom_headers(scope, headers)
                if hasattr(request, "uri_template") and request.uri_template:
                    scope.span.set_tag("http.path_tpl", request.uri_template)
                if hasattr(request, "ctx"):
                    request.ctx.iscope = scope
                print("original span is :", scope.span)
                print("origina async_tracer is :", async_tracer)

        @app.on_response
        def response_with_instana(request, response):
            """Function propagates tracing with Instana
            Args:
                request (HttpRequest): Sanic HttpRequest Object
                response (HttpRequest): Sanic HttpResponse Object
            """

            # Why is 'async_tracer.active_span' None here???
            print("async_tracer is :", async_tracer)
            print("async_tracer.active_span is :", async_tracer.active_span)
            span = request.ctx.iscope.span
            print("span is :", span)
            if span is None:
                return

            status_code = response.status
            if status_code is not None:
                if 500 <= int(status_code) <= 511:
                    span.mark_as_errored()
                span.set_tag('http.status_code', status_code)

            if response.headers is not None:
                async_tracer.inject(span.context, opentracing.Format.HTTP_HEADERS, response.headers)
            response.headers['Server-Timing'] = "intid;desc=%s" % span.context.trace_id
