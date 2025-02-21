# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

"""
Instrumentation for Sanic
https://sanicframework.org/en/
"""

try:
    import sanic
    from instana.log import logger

    if not (hasattr(sanic, "__version__") and sanic.__version__ >= "19.9.0"):
        logger.debug(
            "Instana supports Sanic package versions 19.9.0 and newer.  Skipping."
        )
        raise ImportError

    import wrapt
    from typing import Callable, Tuple, Dict, Any
    from sanic.exceptions import SanicException

    from opentelemetry import context, trace
    from opentelemetry.semconv.trace import SpanAttributes

    from instana.singletons import tracer, agent
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import extract_custom_headers
    from instana.propagators.format import Format

    from sanic.request import Request
    from sanic.response import HTTPResponse

    @wrapt.patch_function_wrapper("sanic.app", "Sanic.__init__")
    def init_with_instana(
        wrapped: Callable[..., sanic.app.Sanic.__init__],
        instance: sanic.app.Sanic,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> None:
        wrapped(*args, **kwargs)
        app = instance

        @app.middleware("request")
        def request_with_instana(request: Request) -> None:
            try:
                if "http" not in request.scheme:
                    return

                headers = request.headers.copy()
                parent_context = tracer.extract(Format.HTTP_HEADERS, headers)

                span = tracer.start_span("asgi", span_context=parent_context)
                request.ctx.span = span

                ctx = trace.set_span_in_context(span)
                token = context.attach(ctx)
                request.ctx.token = token

                span.set_attribute("http.path", request.path)
                span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)
                span.set_attribute(SpanAttributes.HTTP_HOST, request.host)
                if hasattr(request, "url"):
                    span.set_attribute(SpanAttributes.HTTP_URL, request.url)

                query = request.query_string

                if isinstance(query, (str, bytes)) and len(query):
                    if isinstance(query, bytes):
                        query = query.decode("utf-8")
                    scrubbed_params = strip_secrets_from_query(
                        query, agent.options.secrets_matcher, agent.options.secrets_list
                    )
                    span.set_attribute("http.params", scrubbed_params)

                extract_custom_headers(span, headers)
                if hasattr(request, "uri_template") and request.uri_template:
                    span.set_attribute("http.path_tpl", request.uri_template)
            except Exception:
                logger.debug("request_with_instana: ", exc_info=True)

        @app.exception(Exception)
        def exception_with_instana(request: Request, exception: Exception) -> None:
            try:
                if not hasattr(request.ctx, "span"):  # pragma: no cover
                    return
                span = request.ctx.span

                if isinstance(exception, SanicException):
                    # Handle Sanic-specific exceptions
                    status_code = exception.status_code
                    message = str(exception)

                    if all([span, status_code, message]) and 500 <= status_code:
                        span.set_attribute("http.error", message)
            except Exception:
                logger.debug("exception_with_instana: ", exc_info=True)

        @app.middleware("response")
        def response_with_instana(request: Request, response: HTTPResponse) -> None:
            try:
                if not hasattr(request.ctx, "span"):  # pragma: no cover
                    return
                span = request.ctx.span

                status_code = response.status
                if status_code:
                    if int(status_code) >= 500:
                        span.mark_as_errored()
                    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)

                if hasattr(response, "headers"):
                    extract_custom_headers(span, response.headers)
                    tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)

                if span.is_recording():
                    span.end()
                request.ctx.span = None

                if request.ctx.token:
                    context.detach(request.ctx.token)
                    request.ctx.token = None
            except Exception:
                logger.debug("response_with_instana: ", exc_info=True)

except ImportError:
    pass
