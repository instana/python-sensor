# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instrumentation for FastAPI
https://fastapi.tiangolo.com/
"""
try:
    import fastapi
    import os
    import wrapt
    import signal
    from distutils.version import LooseVersion

    from ..log import logger
    from ..util.gunicorn import running_in_gunicorn
    from .asgi import InstanaASGIMiddleware
    from starlette.middleware import Middleware
    from fastapi import HTTPException
    from fastapi.exception_handlers import http_exception_handler

    from instana.singletons import async_tracer

    if hasattr(fastapi, '__version__') and \
        (LooseVersion(fastapi.__version__) >= LooseVersion('0.51.0')):

        async def instana_exception_handler(request, exc):
            """
            We capture FastAPI HTTPException, log the error and pass it on
            to the default exception handler.
            """
            try:
                span = async_tracer.active_span

                if span is not None:
                    if hasattr(exc, 'detail') and (500 <= exc.status_code <= 599):
                        span.set_tag('http.error', exc.detail)
                    span.set_tag('http.status_code', exc.status_code)
            except Exception:
                logger.debug("FastAPI instana_exception_handler: ", exc_info=True)

            return await http_exception_handler(request, exc)

        @wrapt.patch_function_wrapper('fastapi.applications', 'FastAPI.__init__')
        def init_with_instana(wrapped, instance, args, kwargs):
            middleware = kwargs.get('middleware')
            if middleware is None:
                kwargs['middleware'] = [Middleware(InstanaASGIMiddleware)]
            elif isinstance(middleware, list):
                middleware.append(Middleware(InstanaASGIMiddleware))

            exception_handlers = kwargs.get('exception_handlers')
            if exception_handlers is None:
                kwargs['exception_handlers'] = dict()

            if isinstance(kwargs['exception_handlers'], dict):
                kwargs['exception_handlers'][HTTPException] = instana_exception_handler

            return wrapped(*args, **kwargs)

        logger.debug("Instrumenting FastAPI")

        # Reload GUnicorn when we are instrumenting an already running application
        if "INSTANA_MAGIC" in os.environ and running_in_gunicorn():
            os.kill(os.getpid(), signal.SIGHUP)
    else:
        logger.debug("Instana supports FastAPI package versions 0.51.0 and newer.  Skipping.")

except ImportError:
    pass
