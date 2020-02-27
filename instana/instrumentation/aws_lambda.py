import os
import sys
import wrapt

from ..log import logger
from ..singletons import agent, tracer


if os.environ.get("INSTANA_ENDPOINT_URL", False):
    handler = os.environ.get("_HANDLER", False)
    if handler:
        parts = handler.split(".")
        handler_function = parts.pop()
        handler_module = ".".join(parts)

        logger.debug("AWS Lambda: Instrumenting handler %s.%s" % (handler_module, handler_function))

        sys.path.insert(0, '/var/runtime')
        sys.path.insert(0, '/var/task')

        # try:
        #     import importlib
        #     module = importlib.import_module(handler_module, package=None)
        # except ImportError:
        #     logger.warn("Couldn't do the manual import")

        @wrapt.patch_function_wrapper(handler_module, handler_function)
        def lambda_handler_with_instana(wrapped, instance, args, kwargs):
            agent.collector.collect_snapshot(*args)

            result = None
            with tracer.start_active_span("aws.lambda.entry") as scope:
                try:
                    scope.span.set_tag('lambda.arn', agent.collector.context.invoked_function_arn)
                    scope.span.set_tag('lambda.name', agent.collector.context.function_name)
                    scope.span.set_tag('lambda.version', agent.collector.context.function_version)

                    result = wrapped(*args, **kwargs)
                except Exception as e:
                    if scope.span:
                        scope.span.log_exception(e)
                    raise

            agent.collector.shutdown()
            return result
