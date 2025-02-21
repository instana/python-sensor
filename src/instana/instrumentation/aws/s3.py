# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from typing import TYPE_CHECKING, Any, Callable, Dict, Sequence, Type

if TYPE_CHECKING:
    from botocore.client import BaseClient

try:
    import inspect

    import wrapt
    from opentelemetry.semconv.trace import SpanAttributes

    from instana.log import logger
    from instana.util.traceutils import (
        get_tracer_tuple,
        tracing_is_off,
    )

    def s3_inject_method_with_instana(
        wrapped: Callable[..., object],
        instance: Type["BaseClient"],
        arg_list: Sequence[object],
        kwargs: Dict[str, Any],
    ) -> Callable[..., object]:
        # If we're not tracing, just return
        if tracing_is_off():
            return wrapped(*arg_list, **kwargs)

        fas = inspect.getfullargspec(wrapped)
        fas_args = fas.args
        fas_args.remove("self")

        tracer, parent_span, _ = get_tracer_tuple()

        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span("boto3", span_context=parent_context) as span:
            try:
                operation = wrapped.__name__
                span.set_attribute("op", operation)
                span.set_attribute("ep", instance._endpoint.host)
                span.set_attribute("reg", instance._client_config.region_name)

                span.set_attribute(
                    SpanAttributes.HTTP_URL,
                    instance._endpoint.host + ":443/" + operation,
                )
                span.set_attribute(SpanAttributes.HTTP_METHOD, "POST")

                arg_length = len(arg_list)
                if arg_length > 0:
                    payload = {}
                    for index in range(arg_length):
                        if fas_args[index] in ["Filename", "Bucket", "Key"]:
                            payload[fas_args[index]] = arg_list[index]
                    span.set_attribute("payload", payload)
            except Exception:
                logger.debug(
                    "s3_inject_method_with_instana: collect error", exc_info=True
                )

            try:
                return wrapped(*arg_list, **kwargs)
            except Exception as exc:
                span.mark_as_errored({"error": exc})
                raise

    for method in [
        "upload_file",
        "upload_fileobj",
        "download_file",
        "download_fileobj",
    ]:
        wrapt.wrap_function_wrapper(
            "boto3.s3.inject", method, s3_inject_method_with_instana
        )

    logger.debug("Instrumenting boto3")
except ImportError:
    pass
