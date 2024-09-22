# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import wrapt
import functools

from instana.log import logger
from instana.singletons import agent, tracer
from instana.util.secrets import strip_secrets_from_query
from instana.propagators.format import Format
from instana.span.span import get_current_span

try:
    import tornado

    @wrapt.patch_function_wrapper('tornado.httpclient', 'AsyncHTTPClient.fetch')
    def fetch_with_instana(wrapped, instance, argv, kwargs):
        try:
            parent_span = get_current_span()

            # If we're not tracing, just return
            if (not parent_span.is_recording()) or (parent_span.name == "tornado-client"):
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

            parent_context = parent_span.get_span_context() if parent_span else None

            span = tracer.start_span("tornado-client", span_context=parent_context)
            tracer.inject(span.context, Format.HTTP_HEADERS, request.headers)

            # Query param scrubbing
            parts = request.url.split('?')
            if len(parts) > 1:
                cleaned_qp = strip_secrets_from_query(parts[1], agent.options.secrets_matcher,
                                                      agent.options.secrets_list)
                span.set_attribute("http.params", cleaned_qp)

            span.set_attribute("http.url", parts[0])
            span.set_attribute("http.method", request.method)

            future = wrapped(request, **kwargs)

            if future is not None:
                cb = functools.partial(finish_tracing, span=span)
                future.add_done_callback(cb)

            return future
        except Exception:
            logger.debug("tornado fetch", exc_info=True)
            raise


    def finish_tracing(future, span):
        try:
            response = future.result()
            span.set_attribute("http.status_code", response.code)
        except tornado.httpclient.HTTPClientError as e:
            span.set_attribute("http.status_code", e.code)
            span.record_exception(e)
            raise
        finally:
            if span.is_recording():
                span.end()


    logger.debug("Instrumenting tornado client")
except ImportError:
    pass
