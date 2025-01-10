# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


try:
    import tornado

    import wrapt

    from opentelemetry.semconv.trace import SpanAttributes

    from instana.log import logger
    from instana.singletons import agent, tracer
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import extract_custom_headers
    from instana.propagators.format import Format



    @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler._execute')
    def execute_with_instana(wrapped, instance, argv, kwargs):
        try:
            span_context = None
            if hasattr(instance.request.headers, '__dict__') and '_dict' in instance.request.headers.__dict__:
                span_context = tracer.extract(Format.HTTP_HEADERS,
                                                instance.request.headers.__dict__['_dict'])

            span = tracer.start_span("tornado-server", span_context=span_context)

            # Query param scrubbing
            if instance.request.query is not None and len(instance.request.query) > 0:
                cleaned_qp = strip_secrets_from_query(instance.request.query, agent.options.secrets_matcher,
                                                        agent.options.secrets_list)
                span.set_attribute("http.params", cleaned_qp)
            
            url = f"{instance.request.protocol}://{instance.request.host}{instance.request.path}"
            span.set_attribute(SpanAttributes.HTTP_URL, url)
            span.set_attribute(SpanAttributes.HTTP_METHOD, instance.request.method)

            span.set_attribute("handler", instance.__class__.__name__)

            # Request header tracking support
            extract_custom_headers(span, instance.request.headers)

            setattr(instance.request, "_instana", span)

            # Set the context response headers now because tornado doesn't give us a better option to do so
            # later for this request.
            tracer.inject(span.context, Format.HTTP_HEADERS, instance._headers)

            return wrapped(*argv, **kwargs)
        except Exception:
            logger.debug("tornado execute", exc_info=True)


    @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler.set_default_headers')
    def set_default_headers_with_instana(wrapped, instance, argv, kwargs):
        if not hasattr(instance.request, '_instana'):
            return wrapped(*argv, **kwargs)

        span = instance.request._instana
        tracer.inject(span.context, Format.HTTP_HEADERS, instance._headers)


    @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler.on_finish')
    def on_finish_with_instana(wrapped, instance, argv, kwargs):
        try:
            if not hasattr(instance.request, '_instana'):
                return wrapped(*argv, **kwargs)

            span = instance.request._instana
            # Response header tracking support
            extract_custom_headers(span, instance._headers)

            status_code = instance.get_status()

            # Mark 500 responses as errored
            if 500 <= status_code:
                span.mark_as_errored()

            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)
            if span.is_recording():
                span.end()

            return wrapped(*argv, **kwargs)
        except Exception:
            logger.debug("tornado on_finish", exc_info=True)


    @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler.log_exception')
    def log_exception_with_instana(wrapped, instance, argv, kwargs):
        try:
            if not hasattr(instance.request, '_instana'):
                return wrapped(*argv, **kwargs)

            if not isinstance(argv[1], tornado.web.HTTPError):
                span = instance.request._instana
                span.record_exception(argv[0])

            return wrapped(*argv, **kwargs)
        except Exception:
            logger.debug("tornado log_exception", exc_info=True)


    logger.debug("Instrumenting tornado server")
except ImportError:
    pass
