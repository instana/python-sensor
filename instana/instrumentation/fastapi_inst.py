"""
Instrumentation for FastAPI
https://fastapi.tiangolo.com/
"""
try:
    import fastapi
    import wrapt
    from ..log import logger
    from .asgi import InstanaASGIMiddleware
    from starlette.middleware import Middleware

    @wrapt.patch_function_wrapper('fastapi.applications', 'FastAPI.__init__')
    def init_with_instana(wrapped, instance, args, kwargs):
        middleware = kwargs.get('middleware')
        if middleware is None:
            kwargs['middleware'] = [Middleware(InstanaASGIMiddleware)]
        elif isinstance(middleware, list):
            middleware.append(Middleware(InstanaASGIMiddleware))

        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting FastAPI")
except ImportError:
    pass