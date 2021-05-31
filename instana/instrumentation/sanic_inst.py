# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

"""
Instrumentation for Sanic
https://sanicframework.org/en/
"""
try:
    import sanic
    import wrapt
    import opentracing
    from ..log import logger
    from ..singletons import async_tracer, agent
    from ..util.secrets import strip_secrets_from_query
    from ..util.traceutils import extract_custom_headers


    @wrapt.patch_function_wrapper('sanic.exceptions', 'SanicException.__init__')
    def exception_with_instana(wrapped, instance, args, kwargs):
        message = kwargs.get("message", args[0])
        status_code = kwargs.get("status_code")
        span = async_tracer.active_span

        if all([span, status_code, message]) and (500 <= status_code <= 599):
            span.set_tag("http.error", message)
            try:
                wrapped(*args, **kwargs)
            except Exception as exc:
                span.log_exception(exc)
        else:
            wrapped(*args, **kwargs)


    def response_details(span, response):
        try:
            status_code = response.status
            if status_code is not None:
                if 500 <= int(status_code) <= 511:
                    span.mark_as_errored()
                span.set_tag('http.status_code', status_code)

            if response.headers is not None:
                async_tracer.inject(span.context, opentracing.Format.HTTP_HEADERS, response.headers)
            response.headers['Server-Timing'] = "intid;desc=%s" % span.context.trace_id
        except Exception:
            logger.debug("send_wrapper: ", exc_info=True)


    if hasattr(sanic.response.BaseHTTPResponse, "send"):
        @wrapt.patch_function_wrapper('sanic.response', 'BaseHTTPResponse.send')
        async def send_with_instana(wrapped, instance, args, kwargs):
            span = async_tracer.active_span
            if span is None:
                await wrapped(*args, **kwargs)
            else:
                response_details(span=span, response=instance)
                try:
                    await wrapped(*args, **kwargs)
                except Exception as exc:
                    span.log_exception(exc)
                    raise
    else:
        @wrapt.patch_function_wrapper('sanic.server', 'HttpProtocol.write_response')
        def write_with_instana(wrapped, instance, args, kwargs):
            response = args[0]
            span = async_tracer.active_span
            if span is None:
                wrapped(*args, **kwargs)
            else:
                response_details(span=span, response=response)
                try:
                    wrapped(*args, **kwargs)
                except Exception as exc:
                    span.log_exception(exc)
                    raise


        @wrapt.patch_function_wrapper('sanic.server', 'HttpProtocol.stream_response')
        async def stream_with_instana(wrapped, instance, args, kwargs):
            response = args[0]
            span = async_tracer.active_span
            if span is None:
                await wrapped(*args, **kwargs)
            else:
                response_details(span=span, response=response)
                try:
                    await wrapped(*args, **kwargs)
                except Exception as exc:
                    span.log_exception(exc)
                    raise


    @wrapt.patch_function_wrapper('sanic.app', 'Sanic.handle_request')
    async def handle_request_with_instana(wrapped, instance, args, kwargs):

        try:
            request = args[0]
            try:  # scheme attribute is calculated in the sanic handle_request method for v19, not yet present
                if "http" not in request.scheme:
                    return await wrapped(*args, **kwargs)
            except AttributeError:
                pass
            headers = request.headers.copy()
            ctx = async_tracer.extract(opentracing.Format.HTTP_HEADERS, headers)
            with async_tracer.start_active_span("asgi", child_of=ctx) as scope:
                scope.span.set_tag('span.kind', 'entry')
                scope.span.set_tag('http.path', request.path)
                scope.span.set_tag('http.method', request.method)
                scope.span.set_tag('http.host', request.host)
                scope.span.set_tag("http.url", request.url)

                query = request.query_string

                if isinstance(query, (str, bytes)) and len(query):
                    if isinstance(query, bytes):
                        query = query.decode('utf-8')
                    scrubbed_params = strip_secrets_from_query(query, agent.options.secrets_matcher,
                                                               agent.options.secrets_list)
                    scope.span.set_tag("http.params", scrubbed_params)

                if agent.options.extra_http_headers is not None:
                    extract_custom_headers(scope, headers)
                await wrapped(*args, **kwargs)
                if hasattr(request, "uri_template") and request.uri_template:
                    scope.span.set_tag("http.path_tpl", request.uri_template)
                if hasattr(request, "ctx"):  # ctx attribute added in the latest v19 versions
                    request.ctx.iscope = scope
        except Exception as e:
            logger.debug("Sanic framework @ handle_request", exc_info=True)
            return await wrapped(*args, **kwargs)


    logger.debug("Instrumenting Sanic")

except ImportError:
    pass
except AttributeError:
    logger.debug("Not supported Sanic version")
