# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instrumentation for FastAPI
https://fastapi.tiangolo.com/
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple

try:
    import os
    import signal

    import fastapi
    import wrapt
    from fastapi import HTTPException
    from fastapi.exception_handlers import http_exception_handler
    from starlette.middleware import Middleware

    from instana.instrumentation.asgi import InstanaASGIMiddleware
    from instana.log import logger
    from instana.util.gunicorn import running_in_gunicorn
    from instana.util.traceutils import get_tracer_tuple

    from opentelemetry.semconv.trace import SpanAttributes

    if TYPE_CHECKING:
        from starlette.requests import Request
        from starlette.responses import Response

    if not (  # pragma: no cover
        hasattr(fastapi, "__version__")
        and (
            fastapi.__version__[0] > "0" or int(fastapi.__version__.split(".")[1]) >= 51
        )
    ):
        logger.debug(
            "Instana supports FastAPI package versions 0.51.0 and newer.  Skipping."
        )
        raise ImportError

    async def instana_exception_handler(
        request: "Request", exc: HTTPException
    ) -> "Response":
        """
        We capture FastAPI HTTPException, log the error and pass it on
        to the default exception handler.
        """
        try:
            _, span, _ = get_tracer_tuple()

            if span:
                if hasattr(exc, "detail") and 500 <= exc.status_code:
                    span.set_attribute("http.error", exc.detail)
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, exc.status_code)
        except Exception:
            logger.debug("FastAPI instana_exception_handler: ", exc_info=True)

        return await http_exception_handler(request, exc)

    @wrapt.patch_function_wrapper("fastapi.applications", "FastAPI.__init__")
    def init_with_instana(
        wrapped: Callable[..., fastapi.applications.FastAPI.__init__],
        instance: fastapi.applications.FastAPI,
        args: Tuple,
        kwargs: Dict[str, Any],
    ) -> None:
        middleware = kwargs.get("middleware")
        if middleware is None:
            kwargs["middleware"] = [Middleware(InstanaASGIMiddleware)]
        elif isinstance(middleware, list):
            middleware.append(Middleware(InstanaASGIMiddleware))

        exception_handlers = kwargs.get("exception_handlers")
        if exception_handlers is None:
            kwargs["exception_handlers"] = dict()

        if isinstance(kwargs["exception_handlers"], dict):
            kwargs["exception_handlers"][HTTPException] = instana_exception_handler

        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting FastAPI")

    # Reload GUnicorn when we are instrumenting an already running application
    if "INSTANA_MAGIC" in os.environ and running_in_gunicorn():  # pragma: no cover
        os.kill(os.getpid(), signal.SIGHUP)

except ImportError:
    pass
