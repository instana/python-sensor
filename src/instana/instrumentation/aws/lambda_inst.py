# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instrumentation for AWS Lambda functions
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple

if TYPE_CHECKING:
    from instana.agent.aws_lambda import AWSLambdaAgent

try:
    import sys
    import traceback

    import wrapt
    from opentelemetry.semconv.trace import SpanAttributes

    from instana import get_aws_lambda_handler
    from instana.instrumentation.aws.triggers import enrich_lambda_span, get_context
    from instana.log import logger
    from instana.singletons import env_is_aws_lambda, get_agent, get_tracer
    from instana.util.ids import define_server_timing

    def lambda_handler_with_instana(
        wrapped: Callable[..., object],
        instance: object,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        event = args[0]
        agent: "AWSLambdaAgent" = get_agent()
        tracer = get_tracer()

        agent.collector.collect_snapshot(*args)
        incoming_ctx = get_context(tracer, event)

        result = None
        with tracer.start_as_current_span(
            "aws.lambda.entry", span_context=incoming_ctx
        ) as span:
            enrich_lambda_span(agent, span, *args)
            try:
                result = wrapped(*args, **kwargs)

                if isinstance(result, dict):
                    server_timing_value = define_server_timing(span.context.trace_id)
                    if "headers" in result:
                        result["headers"]["Server-Timing"] = server_timing_value
                    elif "multiValueHeaders" in result:
                        result["multiValueHeaders"]["Server-Timing"] = [
                            server_timing_value
                        ]
                    if "statusCode" in result and result.get("statusCode"):
                        status_code = int(result["statusCode"])
                        span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)
                        if 500 <= status_code:
                            span.record_exception(f"HTTP status {status_code}")
            except Exception as exc:
                logger.debug(f"AWS Lambda lambda_handler_with_instana error: {exc}")
                if span:
                    exc = traceback.format_exc()
                    span.record_exception(exc)
                raise
            finally:
                agent.collector.shutdown()

        if agent.collector.started:
            agent.collector.shutdown()

        return result

    if env_is_aws_lambda:
        handler_module, handler_function = get_aws_lambda_handler()

        if handler_module and handler_function:
            try:
                logger.debug(
                    f"Instrumenting AWS Lambda handler ({handler_module}.{handler_function})"
                )
                sys.path.insert(0, "/var/runtime")
                sys.path.insert(0, "/var/task")
                wrapt.wrap_function_wrapper(
                    handler_module, handler_function, lambda_handler_with_instana
                )
            except (ModuleNotFoundError, ImportError) as exc:
                logger.debug(f"AWS Lambda error: {exc}")
                logger.warning(
                    "Instana: Couldn't instrument AWS Lambda handler. Not monitoring."
                )
        else:
            logger.warning(
                "Instana: Couldn't determine AWS Lambda Handler.  Not monitoring."
            )
except ImportError:
    pass
