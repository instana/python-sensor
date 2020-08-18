from __future__ import absolute_import

import opentracing
import wrapt

from ...log import logger
from ...singletons import agent, async_tracer
from ...util import strip_secrets_from_query


try:
    import aiohttp
    import asyncio

    async def stan_request_start(session, trace_config_ctx, params):
        try:
            parent_span = async_tracer.active_span

            # If we're not tracing, just return
            if parent_span is None:
                trace_config_ctx.scope = None
                return

            scope = async_tracer.start_active_span("aiohttp-client", child_of=parent_span)
            trace_config_ctx.scope = scope

            async_tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, params.headers)

            parts = str(params.url).split('?')
            if len(parts) > 1:
                cleaned_qp = strip_secrets_from_query(parts[1], agent.options.secrets_matcher, agent.options.secrets_list)
                scope.span.set_tag("http.params", cleaned_qp)
            scope.span.set_tag("http.url", parts[0])
            scope.span.set_tag('http.method', params.method)
        except Exception:
            logger.debug("stan_request_start", exc_info=True)

    async def stan_request_end(session, trace_config_ctx, params):
        try:
            scope = trace_config_ctx.scope
            if scope is not None:
                scope.span.set_tag('http.status_code', params.response.status)

                if agent.options.extra_http_headers is not None:
                    for custom_header in agent.options.extra_http_headers:
                        if custom_header in params.response.headers:
                            scope.span.set_tag("http.%s" % custom_header, params.response.headers[custom_header])

                if 500 <= params.response.status <= 599:
                    scope.span.mark_as_errored({"http.error": params.response.reason})

                scope.close()
        except Exception:
            logger.debug("stan_request_end", exc_info=True)

    async def stan_request_exception(session, trace_config_ctx, params):
        try:
            scope = trace_config_ctx.scope
            if scope is not None:
                scope.span.log_exception(params.exception)
                scope.span.set_tag("http.error", str(params.exception))
                scope.close()
        except Exception:
            logger.debug("stan_request_exception", exc_info=True)

    @wrapt.patch_function_wrapper('aiohttp.client','ClientSession.__init__')
    def init_with_instana(wrapped, instance, argv, kwargs):
        instana_trace_config = aiohttp.TraceConfig()
        instana_trace_config.on_request_start.append(stan_request_start)
        instana_trace_config.on_request_end.append(stan_request_end)
        instana_trace_config.on_request_exception.append(stan_request_exception)
        if 'trace_configs' in kwargs:
            kwargs['trace_configs'].append(instana_trace_config)
        else:
            kwargs['trace_configs'] = [instana_trace_config]

        return wrapped(*argv, **kwargs)

    logger.debug("Instrumenting aiohttp client")
except ImportError:
    pass

