# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instana ASGI Middleware
"""

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent, tracer
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import extract_custom_headers

if TYPE_CHECKING:
    from starlette.middleware.exceptions import ExceptionMiddleware
    from instana.span.span import InstanaSpan


class InstanaASGIMiddleware:
    """
    Instana ASGI Middleware
    """

    def __init__(self, app: "ExceptionMiddleware") -> None:
        self.app = app

    def _collect_kvs(self, scope: Dict[str, Any], span: "InstanaSpan") -> None:
        try:
            span.set_attribute("http.path", scope.get("path"))
            span.set_attribute(SpanAttributes.HTTP_METHOD, scope.get("method"))

            server = scope.get("server")
            if isinstance(server, tuple) or isinstance(server, list):
                span.set_attribute(SpanAttributes.HTTP_HOST, server[0])

            query = scope.get("query_string")
            if isinstance(query, (str, bytes)) and len(query):
                if isinstance(query, bytes):
                    query = query.decode("utf-8")
                scrubbed_params = strip_secrets_from_query(
                    query, agent.options.secrets_matcher, agent.options.secrets_list
                )
                span.set_attribute("http.params", scrubbed_params)

            app = scope.get("app")
            if app and hasattr(app, "routes"):
                # Attempt to detect the Starlette routes registered.
                # If Starlette isn't present, we harmlessly dump out.
                from starlette.routing import Match

                for route in scope["app"].routes:
                    if route.matches(scope)[0] == Match.FULL:
                        span.set_attribute("http.path_tpl", route.path)
        except Exception:
            logger.debug("ASGI collect_kvs: ", exc_info=True)

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        request_context = None

        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        request_headers = scope.get("headers")
        if isinstance(request_headers, list):
            request_context = tracer.extract(Format.BINARY, request_headers)

        with tracer.start_as_current_span("asgi", span_context=request_context) as span:
            self._collect_kvs(scope, span)
            if "headers" in scope:
                extract_custom_headers(span, scope["headers"])

            instana_send = self._send_with_instana(
                span,
                scope,
                send,
            )

            try:
                await self.app(scope, receive, instana_send)
            except Exception as exc:
                span.record_exception(exc)
                raise exc

    def _send_with_instana(
        self,
        current_span: "InstanaSpan",
        scope: Dict[str, Any],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> Awaitable[None]:
        async def send_wrapper(response: Dict[str, Any]) -> Awaitable[None]:
            if response["type"] == "http.response.start":
                try:
                    status_code = response.get("status")
                    if status_code:
                        if 500 <= int(status_code):
                            current_span.mark_as_errored()
                        current_span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)

                    headers = response.get("headers")
                    if headers:
                        extract_custom_headers(current_span, headers)
                        tracer.inject(current_span.context, Format.BINARY, headers)
                except Exception:
                    logger.debug("ASGI send_wrapper error: ", exc_info=True)

            try:
                await send(response)
            except Exception as exc:
                current_span.record_exception(exc)
                raise

        return send_wrapper
