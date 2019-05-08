from __future__ import absolute_import

import opentracing
import wrapt
import functools
import basictracer
import sys

from ...log import logger
from ...singletons import agent, tornado_tracer
from ...util import strip_secrets

from distutils.version import LooseVersion


# Tornado >=6.0 switched to contextvars for context management.  This requires changes to the opentracing
# scope managers which we will tackle soon.
# Limit Tornado version for the time being.
if (('tornado' in sys.modules) and
        hasattr(sys.modules['tornado'], 'version') and
        (LooseVersion(sys.modules['tornado'].version) < LooseVersion('6.0.0'))):
    try:
        import tornado

        @wrapt.patch_function_wrapper('tornado.httpclient', 'AsyncHTTPClient.fetch')
        def fetch_with_instana(wrapped, instance, argv, kwargs):
            try:
                parent_span = tornado_tracer.active_span

                # If we're not tracing, just return
                if parent_span is None:
                    return wrapped(*argv, **kwargs)

                request = argv[0]

                # To modify request headers, we have to preemptively create an HTTPRequest object if a
                # URL string was passed.
                if not isinstance(request, tornado.httpclient.HTTPRequest):
                    request = tornado.httpclient.HTTPRequest(url=request, **kwargs)

                    new_kwargs = {}
                    for param in ('callback', 'raise_error'):
                        # if not in instead and pop
                        if param in kwargs:
                            new_kwargs[param] = kwargs.pop(param)
                    kwargs = new_kwargs

                if parent_span.operation_name == "tornado-client":
                    # In the case of 3xx responses, the tornado client follows the redirects and calls this
                    # function recursively which ends up chaining HTTP requests.  Here we tie subsequent
                    # calls to the true parent span of the original tornado-client call.
                    ctx = basictracer.context.SpanContext()
                    ctx.trace_id = parent_span.context.trace_id
                    ctx.span_id = parent_span.parent_id
                else:
                    ctx = parent_span.context

                scope = tornado_tracer.start_active_span('tornado-client', child_of=ctx)
                tornado_tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, request.headers)

                # Query param scrubbing
                parts = request.url.split('?')
                if len(parts) > 1:
                    cleaned_qp = strip_secrets(parts[1], agent.secrets_matcher, agent.secrets_list)
                    scope.span.set_tag("http.params", cleaned_qp)

                scope.span.set_tag("http.url", parts[0])
                scope.span.set_tag("http.method", request.method)

                future = wrapped(request, **kwargs)

                if future is not None:
                    cb = functools.partial(finish_tracing, scope=scope)
                    future.add_done_callback(cb)

                return future
            except Exception:
                logger.debug("tornado fetch", exc_info=True)
                raise

        def finish_tracing(future, scope):
            try:
                response = future.result()
                scope.span.set_tag("http.status_code", response.code)
            except tornado.httpclient.HTTPClientError as e:
                scope.span.set_tag("http.status_code", e.code)
                scope.span.log_exception(e)
                raise
            finally:
                scope.close()


        logger.debug("Instrumenting tornado client")
    except ImportError:
        pass

