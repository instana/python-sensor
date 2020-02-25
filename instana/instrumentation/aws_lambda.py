import os
import sys
import wrapt

from ..log import logger
from ..singletons import tracer


if os.environ.get("INSTANA_ENDPOINT_URL", False):
    handler = os.environ.get("_HANDLER", False)
    if handler:
        parts = handler.split(".")
        handler_function = parts.pop()
        handler_module = ".".join(parts)

        logger.debug("AWS Lambda: Instrumenting handler %s.%s" % (handler_module, handler_function))

        sys.path.insert(0, '/var/runtime')
        sys.path.insert(0, '/var/task')

        try:
            import importlib
            module = importlib.import_module(handler_module, package=None)
        except ImportError:
            logger.warn("Couldn't do the manual import")

        @wrapt.patch_function_wrapper(handler_module, handler_function)
        def lambda_handler_with_instana(wrapped, instance, args, kwargs):
            logger.debug("we got the handler!")

            with tracer.start_active_span("aws.lambda.entry") as scope:
                try:
                    result = wrapped(*args, **kwargs)
                except Exception as e:
                    if scope.span:
                        scope.span.log_exception(e)
                    raise
                else:
                    return result
