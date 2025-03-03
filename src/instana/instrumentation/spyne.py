# (c) Copyright IBM Corp. 2025

try:
    import spyne
    import wrapt

    from opentelemetry.semconv.trace import SpanAttributes

    from instana.log import logger
    from instana.singletons import agent, tracer
    from instana.propagators.format import Format
    from instana.util.secrets import strip_secrets_from_query

    
    @wrapt.patch_function_wrapper("spyne.server.wsgi", "WsgiApplication._WsgiApplication__finalize")
    def finalize_with_instana(wrapped, instance, args, kwargs):
        ctx = args[0]
        span = ctx.udc
        if span:
            resp_code = int(ctx.transport.resp_code.split()[0])

            if 500 <= resp_code:
                span.mark_as_errored()

            span.set_attribute(
                SpanAttributes.HTTP_STATUS_CODE, int(resp_code)
            )
            if span.is_recording():
                span.end()

        ctx.udc = None
        return wrapped(*args, **kwargs)


    @wrapt.patch_function_wrapper("spyne.application", "Application.process_request")
    def process_request_with_instana(wrapped, instance, args, kwargs):
        ctx = args[0]
        headers = ctx.in_document
        span_context = tracer.extract(Format.HTTP_HEADERS, headers)

        with tracer.start_as_current_span(
            "spyne", span_context=span_context, end_on_exit=False,
        ) as span:
            if "REQUEST_METHOD" in headers:
                span.set_attribute(SpanAttributes.HTTP_METHOD, headers["REQUEST_METHOD"])
            if "PATH_INFO" in headers:
                span.set_attribute(SpanAttributes.HTTP_URL, headers["PATH_INFO"])
            if "QUERY_STRING" in headers and len(headers["QUERY_STRING"]):
                scrubbed_params = strip_secrets_from_query(
                    headers["QUERY_STRING"],
                    agent.options.secrets_matcher,
                    agent.options.secrets_list,
                )
                span.set_attribute("http.params", scrubbed_params)
            if "HTTP_HOST" in headers:
                span.set_attribute("http.host", headers["HTTP_HOST"])

            response = wrapped(*args, **kwargs)
            ctx = args[0]
            tracer.inject(span.context, Format.HTTP_HEADERS, ctx.transport.resp_headers)

            ## Store the span in the user defined context object offered by Spyne
            ctx.udc = span
            return response

    logger.debug("Instrumenting Spyne")

except ImportError:
    pass
