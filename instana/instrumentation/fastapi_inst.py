"""
Instrumentation for FastAPI
https://fastapi.tiangolo.com/
"""
try:
    import fastapi
    import wrapt
    import signal
    import os

    from ..log import logger
    from ..util import running_in_gunicorn
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

    # Reload GUnicorn when we are instrumenting an already running application
    if "INSTANA_MAGIC" in os.environ and running_in_gunicorn():
        os.kill(os.getpid(), signal.SIGHUP)

except ImportError:
    pass