# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Tuple
import wrapt

from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import get_tracer_tuple, tracing_is_off, extract_custom_headers

try:
    import aiohttp

    if TYPE_CHECKING:
        from aiohttp.client import ClientSession
        from instana.span.span import InstanaSpan


    async def stan_request_start(
        session: "ClientSession", trace_config_ctx: SimpleNamespace, params
    ) -> Awaitable[None]:
        try:
            # If we're not tracing, just return
            if tracing_is_off():
                trace_config_ctx.span_context = None
                return

            tracer, parent_span, _ = get_tracer_tuple()
            parent_context = parent_span.get_span_context() if parent_span else None

            span = tracer.start_span("aiohttp-client", span_context=parent_context)

            extract_custom_headers(span, params.headers)

            tracer.inject(span.context, Format.HTTP_HEADERS, params.headers)

            parts = str(params.url).split("?")
            if len(parts) > 1:
                cleaned_qp = strip_secrets_from_query(
                    parts[1], agent.options.secrets_matcher, agent.options.secrets_list
                )
                span.set_attribute("http.params", cleaned_qp)
            span.set_attribute(SpanAttributes.HTTP_URL, parts[0])
            span.set_attribute(SpanAttributes.HTTP_METHOD, params.method)
            trace_config_ctx.span_context = span
        except Exception:
            logger.debug("aiohttp-client stan_request_start error:", exc_info=True)

    async def stan_request_end(
        session: "ClientSession", trace_config_ctx: SimpleNamespace, params
    ) -> Awaitable[None]:
        try:
            span: "InstanaSpan" = trace_config_ctx.span_context
            if span:
                span.set_attribute(
                    SpanAttributes.HTTP_STATUS_CODE, params.response.status
                )

                extract_custom_headers(span, params.response.headers)

                if 500 <= params.response.status:
                    span.mark_as_errored({"http.error": params.response.reason})

                if span.is_recording():
                    span.end()
                trace_config_ctx = None
        except Exception:
            logger.debug("aiohttp-client stan_request_end error:", exc_info=True)

    async def stan_request_exception(
        session: "ClientSession", trace_config_ctx: SimpleNamespace, params
    ) -> Awaitable[None]:
        try:
            span: "InstanaSpan" = trace_config_ctx.span_context
            if span:
                span.record_exception(params.exception)
                span.set_attribute("http.error", str(params.exception))
                if span.is_recording():
                    span.end()
                trace_config_ctx = None
        except Exception:
            logger.debug("aiohttp-client stan_request_exception error:", exc_info=True)

    @wrapt.patch_function_wrapper("aiohttp.client", "ClientSession.__init__")
    def init_with_instana(
        wrapped: Callable[..., Awaitable["ClientSession"]],
        instance: aiohttp.client.ClientSession,
        args: Tuple[int, str, Tuple[object, ...]],
        kwargs: Dict[str, Any],
    ) -> object:
        instana_trace_config = aiohttp.TraceConfig()
        instana_trace_config.on_request_start.append(stan_request_start)
        instana_trace_config.on_request_end.append(stan_request_end)
        instana_trace_config.on_request_exception.append(stan_request_exception)
        if "trace_configs" in kwargs:
            kwargs["trace_configs"].append(instana_trace_config)
        else:
            kwargs["trace_configs"] = [instana_trace_config]

        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting aiohttp client")
except ImportError:
    pass
