"""
Instrumentation for Starlette
https://www.starlette.io/
"""
try:
    import starlette
    import wrapt
    from ..log import logger
    from .asgi import InstanaASGIMiddleware
    from starlette.middleware import Middleware

    @wrapt.patch_function_wrapper('starlette.applications', 'Starlette.__init__')
    def init_with_instana(wrapped, instance, args, kwargs):
        middleware = kwargs.get('middleware')
        if middleware is None:
            kwargs['middleware'] = [Middleware(InstanaASGIMiddleware)]
        elif isinstance(middleware, list):
            middleware.append(Middleware(InstanaASGIMiddleware))

        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting Starlette")
except ImportError:
    pass
