# (c) Copyright IBM Corp. 2025

try:
    import httpx
    import wrapt
    from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple, Optional
    from opentelemetry.semconv.trace import SpanAttributes
    from opentelemetry.trace import SpanKind

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import agent
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import (
        extract_custom_headers,
        get_tracer_tuple,
        tracing_is_off,
    )

    if TYPE_CHECKING:
        from instana.span.span import InstanaSpan

    def _set_request_span_attributes(
        span: "InstanaSpan",
        request: httpx.Request,
    ) -> None:
        try:
            url = request.url

            # Strip any secrets from potential query params
            if url.query:
                formatted_query = strip_secrets_from_query(
                    str(url.query, encoding="utf-8"),
                    agent.options.secrets_matcher,
                    agent.options.secrets_list,
                )
                span.set_attribute("http.params", formatted_query)

            url_str = f"{url.scheme}://{url.host}"
            if url.port:
                url_str += f":{url.port}"
            url_str += f"{url.path}"

            span.set_attribute(SpanAttributes.HTTP_URL, url_str)
            span.set_attribute(SpanAttributes.HTTP_HOST, url.host)
            span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)
            span.set_attribute("http.path", url.path)

            extract_custom_headers(span, request.headers)
        except Exception:
            logger.debug("httpx _set_request_span_attributes error: ", exc_info=True)

    def _set_response_span_attributes(
        span: "InstanaSpan",
        response: Optional[httpx.Response] = None,
    ) -> None:
        try:
            if response.headers:
                extract_custom_headers(span, response.headers)

            status_code = response.status_code
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)
            if 500 <= status_code:
                span.mark_as_errored()
        except Exception:
            logger.debug("httpx _set_request_span_attributes error: ", exc_info=True)

    @wrapt.patch_function_wrapper("httpx", "HTTPTransport.handle_request")
    def handle_request_with_instana(
        wrapped: Callable[..., "httpx.HTTPTransport.handle_request"],
        instance: httpx.HTTPTransport,
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> httpx.Response:
        # If we're not tracing, just return
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span(
            "httpx", span_context=parent_context, kind=SpanKind.CLIENT
        ) as span:
            try:
                request = args[0]
                _set_request_span_attributes(span, request)
                tracer.inject(span.context, Format.HTTP_HEADERS, request.headers)

                response = wrapped(*args, **kwargs)
                _set_response_span_attributes(span, response)
            except Exception as e:
                span.record_exception(e)
            else:
                return response

    @wrapt.patch_function_wrapper("httpx", "AsyncHTTPTransport.handle_async_request")
    async def handle_async_request_with_instana(
        wrapped: Callable[..., "httpx.AsyncHTTPTransport.handle_async_request"],
        instance: httpx.AsyncHTTPTransport,
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> httpx.Response:
        # If we're not tracing, just return
        if tracing_is_off():
            return await wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span(
            "httpx", span_context=parent_context, kind=SpanKind.CLIENT
        ) as span:
            try:
                request = args[0]
                _set_request_span_attributes(span, request)
                tracer.inject(span.context, Format.HTTP_HEADERS, request.headers)

                response = await wrapped(*args, **kwargs)
                _set_response_span_attributes(span, response)
            except Exception as e:
                span.record_exception(e)
            else:
                return response

    logger.debug("Instrumenting httpx")

except ImportError:
    pass
