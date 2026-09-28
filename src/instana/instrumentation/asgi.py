# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instana ASGI Middleware
"""

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Iterable, Iterator

from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent, get_tracer
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import extract_custom_headers

try:
    from starlette.routing import Match
except ImportError:  # pragma: no cover
    Match = None

try:
    # FastAPI >= 0.137.2
    from fastapi.routing import iter_route_contexts
except ImportError:
    iter_route_contexts = None

if TYPE_CHECKING:
    from starlette.middleware.exceptions import ExceptionMiddleware

    from instana.span.span import InstanaSpan


def _iter_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """
    Yield the routes of an app in a form that can be matched against a scope
    and carries its full path template.

    FastAPI >= 0.137 keeps the routes added with include_router() in a tree
    whose nodes have no path of their own, so the tree has to be flattened.
    """
    if iter_route_contexts is not None:
        # FastAPI >= 0.137.2
        yield from iter_route_contexts(routes)
        return

    for route in routes:
        if hasattr(route, "effective_route_contexts"):
            # FastAPI 0.137.0 and 0.137.1
            yield from route.effective_route_contexts()
        else:
            # FastAPI < 0.137 and Starlette: the routes are already flat
            yield route


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
            if isinstance(server, (tuple, list)):
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
                for route in _iter_routes(app.routes):
                    if route.matches(scope)[0] == Match.FULL:
                        path_tpl = getattr(route, "path", None)
                        if path_tpl:
                            span.set_attribute("http.path_tpl", path_tpl)
        except Exception:
            logger.debug("ASGI collect_kvs: ", exc_info=True)

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        request_context = None
        tracer = get_tracer()

        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        request_headers = scope.get("headers")
        if isinstance(request_headers, list):
            request_context = tracer.extract(Format.BINARY, request_headers)

        with tracer.start_as_current_span("asgi", context=request_context) as span:
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
                        if int(status_code) >= 500:
                            current_span.mark_as_errored()
                        current_span.set_attribute(
                            SpanAttributes.HTTP_STATUS_CODE, status_code
                        )

                    headers = response.get("headers")
                    if headers:
                        extract_custom_headers(current_span, headers)
                        tracer = get_tracer()
                        tracer.inject(current_span.context, Format.BINARY, headers)
                except Exception:
                    logger.debug("ASGI send_wrapper error: ", exc_info=True)

            try:
                await send(response)
            except Exception as exc:
                current_span.record_exception(exc)
                raise

        return send_wrapper
