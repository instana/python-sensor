from typing import Tuple
import opentracing
from ..log import logger
from ..singletons import async_tracer, agent
from ..util import strip_secrets_from_query

class InstanaASGIMiddleware:
    def __init__(self, app):
        logger.warn("asgi monkey lives")
        self.app = app

    def collect_kvs(self, scope, span):
        span.set_tag('http.path', scope.get('path'))
        span.set_tag('http.method', scope.get('method'))

        server = scope.get('server')
        if isinstance(server, Tuple):
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
        logger.warn("scope: %s", scope)

        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_headers = scope.get('headers')
        if isinstance(request_headers, list):
            request_context = async_tracer.extract(opentracing.Format.HTTP_HEADERS, request_headers)

        def send_wrapper(response):
            span = async_tracer.active_span
            sc = response.get('status')
            if sc is not None:
                if 500 <= int(sc) <= 511:
                    span.mark_as_errored()
                span.set_tag('http.status_code', sc)

            # {'type': 'http.response.start', 'status': 200, 'headers': [(b'content-length', b'25'), (b'content-type', b'application/json')]}
            # {'type': 'http.response.body', 'body': b'{"message":"Hello World"}'}

            if 'headers' in response:
                async_tracer.inject(span.context, opentracing.Format.HTTP_HEADERS, response['headers'])
                response['headers'].append(('Server-Timing', "intid;desc=%s" % span.context.trace_id))

            logger.debug("response is: %s" % response)
            return send(response)

        with async_tracer.start_active_span("asgi", child_of=request_context) as tracing_scope:
            if 'headers' in scope and agent.options.extra_http_headers is not None:
                for custom_header in agent.options.extra_http_headers:
                    # Headers are in the following format: b'x-header-1'
                    for header_pair in scope['headers']:
                        if header_pair[0].decode('utf-8').lower() == custom_header.lower():
                            tracing_scope.span.set_tag("http.%s" % custom_header, header_pair[1].decode('utf-8'))

            self.collect_kvs(scope, tracing_scope.span)

            await self.app(scope, receive, send_wrapper)