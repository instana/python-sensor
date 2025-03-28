# (c) Copyright IBM Corp. 2025

try:
    from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple, Optional

    import wrapt
    from opentelemetry.semconv.trace import SpanAttributes
    from opentelemetry.trace import SpanKind

    import httpx
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

    def _set_span_attributes(
        span: "InstanaSpan",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
        response: Optional[httpx.Response] = None,
    ) -> None:
        kvs = _collect_request_args(args, kwargs)
        if "host" in kvs:
            span.set_attribute(SpanAttributes.HTTP_HOST, kvs["host"])
        if "url" in kvs:
            span.set_attribute(SpanAttributes.HTTP_URL, kvs["url"])
        if "query" in kvs:
            span.set_attribute("http.params", kvs["query"])
        if "method" in kvs:
            span.set_attribute(SpanAttributes.HTTP_METHOD, kvs["method"])
        if "path" in kvs:
            span.set_attribute("http.path", kvs["path"])
        if "headers" in kvs:
            extract_custom_headers(span, kvs["headers"])

        resp = _collect_response(response)
        if "status_code" in resp:
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, resp["status_code"])
        if "headers" in resp:
            extract_custom_headers(span, resp["headers"])
        if 500 <= resp["status_code"]:
            span.mark_as_errored()

    def _collect_request_args(
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        kvs = dict()
        try:
            if isinstance(args[0], httpx.Request):
                kvs["host"] = args[0].url.host
                kvs["port"] = args[0].url.port
                kvs["method"] = args[0].method
                kvs["path"] = args[0].url.path

                # Strip any secrets from potential query params
                if args[0].url.query:
                    kvs["query"] = strip_secrets_from_query(
                        str(args[0].url.query, encoding='utf-8'),
                        agent.options.secrets_matcher,
                        agent.options.secrets_list,
                    )

                url = f"{args[0].url.scheme}://{kvs["host"]}"
                if kvs["port"]:
                    url += f":{kvs["port"]}"
                url += f"{kvs["path"]}"
                kvs["url"] = url

            if "headers" in kwargs:
                kvs["headers"] = kwargs["headers"].copy()
        except Exception:
            logger.debug("httpx _collect_request_args error: ", exc_info=True)
        finally:
            return kvs

    def _collect_response(
        response: httpx.Response
    ) -> Dict[str, Any]:
        kvs = dict()
        try:
            kvs["status_code"] = response.status_code
            if response.headers:
                kvs["headers"] = response.headers.copy()
        except Exception:
            logger.debug("httpx _collect_response error: ", exc_info=True)
        finally:
            return kvs

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

        tracer, parent_span, span_name = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span(
            "httpx", span_context=parent_context, kind=SpanKind.CLIENT
        ) as span:
            try:
                if "headers" in kwargs:
                    tracer.inject(span.context, Format.HTTP_HEADERS, kwargs["headers"])
      
                response = wrapped(*args, **kwargs)
                _set_span_attributes(span, args, kwargs, response)
            except Exception as e:
                span.record_exception(e)
            else:
                return response

    logger.debug("Instrumenting httpx")
except ImportError:
    pass
