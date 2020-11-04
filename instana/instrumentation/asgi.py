import opentracing
from ..log import logger
from ..singletons import async_tracer, agent
from ..util import strip_secrets_from_query
from starlette.routing import Match

class InstanaASGIMiddleware:
    def __init__(self, app):
        logger.warn("asgi monkey lives")
        self.app = app

    def extract_custom_headers(self, span, headers):
        try:
            for custom_header in agent.options.extra_http_headers:
                # Headers are in the following format: b'x-header-1'
                for header_pair in headers:
                    if header_pair[0].decode('utf-8').lower() == custom_header.lower():
                        span.set_tag("http.%s" % custom_header, header_pair[1].decode('utf-8'))
        except Exception:
            logger.debug("extract_custom_headers: ", exc_info=True)

    def collect_kvs(self, scope, span):
        span.set_tag('http.path', scope.get('path'))
        span.set_tag('http.method', scope.get('method'))

        server = scope.get('server')
        if isinstance(server, tuple):
            span.set_tag('http.host', server[0])
            # span.set_tag('http.port', server[1])

        query = scope.get('query_string')
        if isinstance(query, (str, bytes)) and len(query):
            if isinstance(query, bytes):
                query = query.decode('utf-8')
            scrubbed_params = strip_secrets_from_query(query, agent.options.secrets_matcher, agent.options.secrets_list)
            span.set_tag("http.params", scrubbed_params)

    async def __call__(self, scope, receive, send):
        request_context = None

        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_headers = scope.get('headers')
        if isinstance(request_headers, list):
            request_context = async_tracer.extract(opentracing.Format.BINARY, request_headers)

        async def send_wrapper(response):
            try:
                span = async_tracer.active_span
                sc = response.get('status')
                if sc is not None:
                    if 500 <= int(sc) <= 511:
                        span.mark_as_errored()
                    span.set_tag('http.status_code', sc)

                if response['type'] == 'http.response.start' and 'headers' in response:
                    async_tracer.inject(span.context, opentracing.Format.BINARY, response['headers'])

                logger.debug("response is: %s", response)
                await send(response)
            except Exception:
                logger.debug("send_wrapper: ", exc_info=True)

        with async_tracer.start_active_span("asgi", child_of=request_context) as tracing_scope:
            try:
                if 'headers' in scope and agent.options.extra_http_headers is not None:
                    self.extract_custom_headers(tracing_scope.span, scope['headers'])

                for route in scope['app'].routes:
                    if route.matches(scope)[0] == Match.FULL:
                        tracing_scope.span.set_tag("http.path_tpl", route.path)

                self.collect_kvs(scope, tracing_scope.span)
            except Exception:
                logger.debug("ASGI __call__: ", exc_info=True)

            await self.app(scope, receive, send_wrapper)
