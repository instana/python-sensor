# (c) Copyright IBM Corp. 2026

try:
    from typing import TYPE_CHECKING, Any, Callable, Optional

    import wrapt
    from opentelemetry import context, trace

    if TYPE_CHECKING:
        from twisted.web.http import Request
        from twisted.web.resource import Resource

    from opentelemetry.semconv.trace import SpanAttributes

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import agent, get_tracer
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import extract_custom_headers

    @wrapt.patch_function_wrapper("twisted.web.resource", "Resource.render")
    def render_with_instana(
        wrapped: Callable[..., Any],
        instance: "Resource",
        argv: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Optional[bytes]:
        try:
            request: "Request" = argv[0]
            tracer = get_tracer()

            # Extract parent context from incoming request headers
            parent_context = None
            if request.requestHeaders:
                headers_dict: dict[str, str] = {
                    k.decode("latin-1"): v[0].decode("utf-8")
                    for k, v in request.requestHeaders.getAllRawHeaders()
                }
                parent_context = tracer.extract(Format.HTTP_HEADERS, headers_dict)

            span = tracer.start_span("twisted-server", context=parent_context)

            # Set span as current so downstream code (e.g. twisted-client) can find it
            ctx = trace.set_span_in_context(span)
            token = context.attach(ctx)
            request._instana_token = token

            # Extract the URL components
            host = request.getHeader("host") or ""
            scheme = "https" if request.isSecure() else "http"
            raw_path = request.path
            path = (
                raw_path.decode("latin-1") if isinstance(raw_path, bytes) else raw_path
            )

            url = f"{scheme}://{host}{path}"
            span.set_attribute(SpanAttributes.HTTP_URL, url)

            raw_method = request.method
            method = (
                raw_method.decode("latin-1")
                if isinstance(raw_method, bytes)
                else raw_method
            )
            span.set_attribute(SpanAttributes.HTTP_METHOD, method)

            # Query param scrubbing
            raw_query = request.uri
            query = (
                raw_query.decode("latin-1")
                if isinstance(raw_query, bytes)
                else raw_query
            )
            if "?" in query:
                qs = query.split("?", 1)[1]
                if qs:
                    cleaned_qp = strip_secrets_from_query(
                        qs,
                        agent.options.secrets_matcher,
                        agent.options.secrets_list,
                    )
                    span.set_attribute("http.params", cleaned_qp)

            # Request header tracking support
            extract_custom_headers(span, headers_dict)

            # Inject correlation headers into response
            response_headers = {}
            tracer.inject(span.context, Format.HTTP_HEADERS, response_headers)
            for key, value in response_headers.items():
                request.setHeader(key.encode("latin-1"), value.encode("utf-8"))

            # Store span on request for later retrieval
            request._instana = span

            # Wrap request.finish to close the span when the response is complete
            original_finish = request.finish

            def finish_with_instana() -> None:
                try:
                    _span = request._instana
                    status_code = request.code
                    if isinstance(status_code, int):
                        _span.set_attribute(
                            SpanAttributes.HTTP_STATUS_CODE, status_code
                        )
                        if status_code >= 500:
                            _span.mark_as_errored()

                    # Capture response headers
                    response_hdrs = {
                        k.decode("latin-1"): v[0].decode("utf-8")
                        for k, v in request.responseHeaders.getAllRawHeaders()
                    }
                    extract_custom_headers(_span, response_hdrs)

                    if _span.is_recording():
                        _span.end()
                except Exception:
                    logger.debug("twisted finish_with_instana", exc_info=True)
                finally:
                    context.detach(request._instana_token)
                    original_finish()

            request.finish = finish_with_instana

            return wrapped(*argv, **kwargs)
        except Exception:
            logger.debug("twisted render_with_instana", exc_info=True)
            return wrapped(*argv, **kwargs)

    logger.debug("Instrumenting twisted server")
except ImportError:
    pass
