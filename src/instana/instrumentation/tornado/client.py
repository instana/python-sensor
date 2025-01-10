# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

try:
    import tornado

    import wrapt
    import functools
    from typing import TYPE_CHECKING, Dict, Any

    from opentelemetry.semconv.trace import SpanAttributes

    from instana.log import logger
    from instana.singletons import agent, tracer
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import extract_custom_headers
    from instana.propagators.format import Format
    from instana.span.span import get_current_span


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

            extract_custom_headers(span, request.headers)

            tracer.inject(span.context, Format.HTTP_HEADERS, request.headers)

            # Query param scrubbing
            parts = request.url.split('?')
            if len(parts) > 1:
                cleaned_qp = strip_secrets_from_query(parts[1], agent.options.secrets_matcher,
                                                      agent.options.secrets_list)
                span.set_attribute("http.params", cleaned_qp)

            span.set_attribute(SpanAttributes.HTTP_URL, parts[0])
            span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)

            future = wrapped(request, **kwargs)

            if future is not None:
                cb = functools.partial(finish_tracing, span=span)
                future.add_done_callback(cb)

            return future
        except Exception:
            logger.debug("Tornado fetch_with_instana: ", exc_info=True)


    def finish_tracing(future, span):
        try:
            response = future.result()
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.code)

            extract_custom_headers(span, response.headers)
        except tornado.httpclient.HTTPClientError as e:
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, e.code)
            span.record_exception(e)
            logger.debug("Tornado finish_tracing HTTPClientError: ", exc_info=True)
        finally:
            if span.is_recording():
                span.end()


    logger.debug("Instrumenting tornado client")
except ImportError:
    pass
