from __future__ import absolute_import

import opentracing
import wrapt

from ...log import logger
from ...singletons import agent, async_tracer
from ...util import strip_secrets


try:
    import aiohttp
    import asyncio

    from aiohttp.web import middleware

    @middleware
    async def stan_middleware(request, handler):
        try:
            ctx = async_tracer.extract(opentracing.Format.HTTP_HEADERS, request.headers)
            request['scope'] = async_tracer.start_active_span('aiohttp-server', child_of=ctx)
            scope = request['scope']

            # Query param scrubbing
            url = str(request.url)
            parts = url.split('?')
            if len(parts) > 1:
                cleaned_qp = strip_secrets(parts[1], agent.secrets_matcher, agent.secrets_list)
                scope.span.set_tag("http.params", cleaned_qp)

            scope.span.set_tag("http.url", parts[0])
            scope.span.set_tag("http.method", request.method)

            # Custom header tracking support
            if agent.extra_headers is not None:
                for custom_header in agent.extra_headers:
                    if custom_header in request.headers:
                        scope.span.set_tag("http.%s" % custom_header, request.headers[custom_header])

            response = await handler(request)

            if response is not None:
                # Mark 500 responses as errored
                if 500 <= response.status <= 511:
                    scope.span.set_tag("error", True)
                    ec = scope.span.tags.get('ec', 0)
                    if ec is 0:
                        scope.span.set_tag("ec", ec + 1)

                scope.span.set_tag("http.status_code", response.status)
                async_tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, response.headers)
                response.headers['Server-Timing'] = "intid;desc=%s" % scope.span.context.trace_id

            return response
        except:
            logger.debug("aiohttp stan_middleware", exc_info=True)
        finally:
            if scope is not None:
                scope.close()


    @wrapt.patch_function_wrapper('aiohttp.web','Application.__init__')
    def init_with_instana(wrapped, instance, argv, kwargs):
        if "middlewares" in kwargs:
            kwargs["middlewares"].append(stan_middleware)
        else:
            kwargs["middlewares"] = [stan_middleware]

        return wrapped(*argv, **kwargs)

    logger.debug("Instrumenting aiohttp server")
except ImportError:
    pass

