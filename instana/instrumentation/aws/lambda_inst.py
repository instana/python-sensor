"""
Instrumentation for AWS Lambda functions
"""
import os
import sys
import wrapt

from .triggers import enrich_lambda_span, get_context

from ...log import logger
from ...singletons import get_agent, get_tracer
from ... import get_lambda_handler_or_default


def lambda_handler_with_instana(wrapped, instance, args, kwargs):
    event = args[0]
    context = args[1]
    agent = get_agent()
    tracer = get_tracer()

    agent.collector.collect_snapshot(*args)
    incoming_ctx = get_context(tracer, event)

    result = None
    with tracer.start_active_span("aws.lambda.entry", child_of=incoming_ctx) as scope:
        enrich_lambda_span(agent, scope.span, *args)
        try:
            result = wrapped(*args, **kwargs)
        except Exception as exc:
            if scope.span:
                scope.span.log_exception(exc)
            raise

    agent.collector.shutdown()
    return result


if os.environ.get("INSTANA_ENDPOINT_URL", False):
    handler_module, handler_function = get_lambda_handler_or_default()

    if handler_module is not None and handler_function is not None:
        logger.debug("Instrumenting AWS Lambda handler (%s.%s)" % (handler_module, handler_function))
        sys.path.insert(0, '/var/runtime')
        sys.path.insert(0, '/var/task')
        wrapt.wrap_function_wrapper(handler_module, handler_function, lambda_handler_with_instana)
    else:
        logger.debug("Couldn't determine AWS Lambda Handler.  Not monitoring.")
