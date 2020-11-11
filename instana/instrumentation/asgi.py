"""
Instana ASGI Middleware
"""
import opentracing

from ..log import logger
from ..singletons import async_tracer, agent
from ..util import strip_secrets_from_query

class InstanaASGIMiddleware:
    """
    Instana ASGI Middleware
    """
    def __init__(self, app):
        self.app = app

    def _extract_custom_headers(self, span, headers):
        try:
            for custom_header in agent.options.extra_http_headers:
                # Headers are in the following format: b'x-header-1'
                for header_pair in headers:
                    if header_pair[0].decode('utf-8').lower() == custom_header.lower():
                        span.set_tag("http.%s" % custom_header, header_pair[1].decode('utf-8'))
        except Exception:
            logger.debug("extract_custom_headers: ", exc_info=True)

    def _collect_kvs(self, scope, span):
        try:
            span.set_tag('span.kind', 'entry')
            span.set_tag('http.path', scope.get('path'))
            span.set_tag('http.method', scope.get('method'))

            server = scope.get('server')
            if isinstance(server, tuple):
                span.set_tag('http.host', server[0])

            query = scope.get('query_string')
            if isinstance(query, (str, bytes)) and len(query):
                if isinstance(query, bytes):
                    query = query.decode('utf-8')
                scrubbed_params = strip_secrets_from_query(query, agent.options.secrets_matcher, agent.options.secrets_list)
                span.set_tag("http.params", scrubbed_params)

            app = scope.get('app')
            if app is not None and hasattr(app, 'routes'):
                # Attempt to detect the Starlette routes registered.
                # If Starlette isn't present, we harmlessly dump out.
                from starlette.routing import Match
                for route in scope['app'].routes:
                    if route.matches(scope)[0] == Match.FULL:
                        span.set_tag("http.path_tpl", route.path)
        except Exception:
            logger.debug("ASGI collect_kvs: ", exc_info=True)


    async def __call__(self, scope, receive, send):
        request_context = None

        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_headers = scope.get('headers')
        if isinstance(request_headers, list):
            request_context = async_tracer.extract(opentracing.Format.BINARY, request_headers)

        async def send_wrapper(response):
            span = async_tracer.active_span
            if span is None:
                await send(response)
            else:
                if response['type'] == 'http.response.start':
                    try:
                        status_code = response.get('status')
                        if status_code is not None:
                            if 500 <= int(status_code) <= 511:
                                span.mark_as_errored()
                            span.set_tag('http.status_code', status_code)

                        headers = response.get('headers')
                        if headers is not None:
                            async_tracer.inject(span.context, opentracing.Format.BINARY, headers)
                    except Exception:
                        logger.debug("send_wrapper: ", exc_info=True)

                try:
                    await send(response)
                except Exception as exc:
                    span.log_exception(exc)
                    raise

        with async_tracer.start_active_span("asgi", child_of=request_context) as tracing_scope:
            self._collect_kvs(scope, tracing_scope.span)
            if 'headers' in scope and agent.options.extra_http_headers is not None:
                self._extract_custom_headers(tracing_scope.span, scope['headers'])

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as exc:
                tracing_scope.span.log_exception(exc)
                raise exc
