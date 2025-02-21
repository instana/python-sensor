# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instrumentation for Starlette
https://www.starlette.io/
"""

from typing import Any, Callable, Dict, Tuple

try:
    import starlette
    import wrapt
    from starlette.middleware import Middleware
    import starlette.applications

    from instana.instrumentation.asgi import InstanaASGIMiddleware
    from instana.log import logger

    @wrapt.patch_function_wrapper("starlette.applications", "Starlette.__init__")
    def init_with_instana(
        wrapped: Callable[..., starlette.applications.Starlette.__init__],
        instance: starlette.applications.Starlette,
        args: Tuple,
        kwargs: Dict[str, Any],
    ) -> None:
        middleware = kwargs.get("middleware")
        if middleware is None:
            kwargs["middleware"] = [Middleware(InstanaASGIMiddleware)]
        elif isinstance(middleware, list):
            middleware.append(Middleware(InstanaASGIMiddleware))

        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting Starlette")

except ImportError:
    pass
