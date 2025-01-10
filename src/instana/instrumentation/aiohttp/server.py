# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Tuple

import wrapt
from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent, tracer
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import extract_custom_headers

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan

try:
    import aiohttp
    from aiohttp.web import middleware

    if TYPE_CHECKING:
        import aiohttp.web

    @middleware
    async def stan_middleware(
        request: "aiohttp.web.Request",
        handler: Callable[..., object],
    ) -> Awaitable["aiohttp.web.Response"]:
        try:
            span_context = tracer.extract(Format.HTTP_HEADERS, request.headers)
            span: "InstanaSpan" = tracer.start_span(
                "aiohttp-server", span_context=span_context
            )
            request["span"] = span

            # Query param scrubbing
            url = str(request.url)
            parts = url.split("?")
            if len(parts) > 1:
                cleaned_qp = strip_secrets_from_query(
                    parts[1], agent.options.secrets_matcher, agent.options.secrets_list
                )
                span.set_attribute("http.params", cleaned_qp)

            span.set_attribute(SpanAttributes.HTTP_URL, parts[0])
            span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)

            extract_custom_headers(span, request.headers)

            response = None
            try:
                response = await handler(request)
            except aiohttp.web.HTTPException as exc:
                # AIOHTTP uses exceptions for specific responses
                # see https://docs.aiohttp.org/en/latest/web_exceptions.html#web-server-exceptions
                response = exc

            if response is not None:
                # Mark 500 responses as errored
                if 500 <= response.status:
                    span.mark_as_errored()

                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status)

                extract_custom_headers(span, response.headers)

                tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)

            return response
        except Exception as exc:
            logger.debug("aiohttp server stan_middleware:", exc_info=True)
            if span:
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 500)
                span.record_exception(exc)
            raise
        finally:
            if span and span.is_recording():
                span.end()

    @wrapt.patch_function_wrapper("aiohttp.web", "Application.__init__")
    def init_with_instana(
        wrapped: Callable[..., "aiohttp.web.Application.__init__"],
        instance: "aiohttp.web.Application",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> object:
        if "middlewares" in kwargs:
            kwargs["middlewares"].insert(0, stan_middleware)
        else:
            kwargs["middlewares"] = [stan_middleware]

        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting aiohttp server")
except ImportError:
    pass
