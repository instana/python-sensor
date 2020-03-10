import os
import sys
import wrapt

from ..log import logger
from ..singletons import get_agent, get_tracer
from .. import get_lambda_handler_or_default


def get_context(tracer, event):
    # TODO: Search for more types of trigger context
    return tracer.extract('http_headers', event)


def _is_api_gateway_proxy_trigger(event):
    for key in ["resource", "path", "httpMethod"]:
        if key not in event:
            return False
    return True


def enrich_lambda_span(agent, span, event, context):
    try:
        span.set_tag('lambda.arn', context.invoked_function_arn)
        span.set_tag('lambda.name', context.function_name)
        span.set_tag('lambda.version', context.function_version)

        if _is_api_gateway_proxy_trigger(event):
            span.set_tag('lambda.trigger', 'aws:api.gateway')
            span.set_tag('http.method', event["httpMethod"])
            span.set_tag('http.url', event["path"])
            span.set_tag('http.path_tpl', event["resource"])
            span.set_tag('http.params', event["httpMethod"])

            if hasattr(agent, 'extra_headers') and agent.extra_headers is not None:
                for custom_header in agent.extra_headers:
                    for key in event:
                        if key.lower() == custom_header:
                            span.set_tag("http.%s" % custom_header, event[key])
    except:
        logger.debug("enrich_lambda_span: ", exc_info=True)


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
        except Exception as e:
            if scope.span:
                scope.span.log_exception(e)
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
