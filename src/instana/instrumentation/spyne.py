# (c) Copyright IBM Corp. 2025

try:
    import spyne
    import wrapt
    from typing import TYPE_CHECKING, Dict, Any, Callable, Tuple, Iterable, Type, Optional

    from types import SimpleNamespace

    from instana.log import logger
    from instana.singletons import agent, tracer
    from instana.propagators.format import Format
    from instana.util.secrets import strip_secrets_from_query

    if TYPE_CHECKING:
        from instana.span.span import InstanaSpan
        from spyne.application import Application
        from spyne.server.wsgi import WsgiApplication

    def set_span_attributes(span: "InstanaSpan", headers: Dict[str, Any]) -> None:
        if "PATH_INFO" in headers:
            span.set_attribute("rpc.call", headers["PATH_INFO"])
        if "QUERY_STRING" in headers and len(headers["QUERY_STRING"]):
            scrubbed_params = strip_secrets_from_query(
                headers["QUERY_STRING"],
                agent.options.secrets_matcher,
                agent.options.secrets_list,
            )
            span.set_attribute("rpc.params", scrubbed_params)
        if "REMOTE_ADDR" in headers:
            span.set_attribute("rpc.host", headers["REMOTE_ADDR"])
        if "SERVER_PORT" in headers:
            span.set_attribute("rpc.port", headers["SERVER_PORT"])

    def record_error(span: "InstanaSpan", response_string: str, error: Optional[Type[Exception]]) -> None:
        resp_code = int(response_string.split()[0])

        if 500 <= resp_code:
            span.record_exception(error)


    @wrapt.patch_function_wrapper("spyne.server.wsgi", "WsgiApplication.handle_error")
    def handle_error_with_instana(
        wrapped: Callable[..., Iterable[object]],
        instance: "WsgiApplication",
        args: Tuple[object],
        kwargs: Dict[str, Any],
    ) -> Iterable[object]:
        ctx = args[0]

        # span created inside process_request() will be handled by finalize() method
        if ctx.udc and ctx.udc.span:
            return wrapped(*args, **kwargs)

        headers = ctx.transport.req_env
        span_context = tracer.extract(Format.HTTP_HEADERS, headers)

        with tracer.start_as_current_span("rpc-server", span_context=span_context) as span:
            set_span_attributes(span, headers)

            response_headers = ctx.transport.resp_headers

            tracer.inject(span.context, Format.HTTP_HEADERS, response_headers)

            response = wrapped(*args, **kwargs)

            record_error(span, ctx.transport.resp_code, ctx.in_error or ctx.out_error)
            return response

    @wrapt.patch_function_wrapper(
        "spyne.server.wsgi", "WsgiApplication._WsgiApplication__finalize"
    )
    def finalize_with_instana(
        wrapped: Callable[..., Tuple[()]],
        instance: "WsgiApplication",
        args: Tuple[object],
        kwargs: Dict[str, Any],
    ) -> Tuple[()]:
        ctx = args[0]
        response_string = ctx.transport.resp_code

        if ctx.udc and ctx.udc.span and response_string:
            span = ctx.udc.span
            record_error(span, response_string, ctx.in_error or ctx.out_error)
            if span.is_recording():
                span.end()

            ctx.udc.span = None
        return wrapped(*args, **kwargs)

    @wrapt.patch_function_wrapper("spyne.application", "Application.process_request")
    def process_request_with_instana(
        wrapped: Callable[..., None],
        instance: "Application",
        args: Tuple[object],
        kwargs: Dict[str, Any],
    ) -> None:
        ctx = args[0]
        headers = ctx.transport.req_env
        span_context = tracer.extract(Format.HTTP_HEADERS, headers)

        with tracer.start_as_current_span(
            "rpc-server",
            span_context=span_context,
            end_on_exit=False,
        ) as span:
            set_span_attributes(span, headers)

            response = wrapped(*args, **kwargs)
            response_headers = ctx.transport.resp_headers

            tracer.inject(span.context, Format.HTTP_HEADERS, response_headers)

            ## Store the span in the user defined context object offered by Spyne
            if ctx.udc:
                ctx.udc.span = span
            else:
                ctx.udc = SimpleNamespace()
                ctx.udc.span = span
            return response

    logger.debug("Instrumenting Spyne")

except ImportError:
    pass
