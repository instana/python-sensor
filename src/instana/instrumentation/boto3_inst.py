# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import json
import wrapt
import inspect
from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple, Sequence, Type, Optional
from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.singletons import tracer, agent
from instana.util.traceutils import get_tracer_tuple, tracing_is_off
from instana.propagators.format import Format
from instana.span.span import get_current_span

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan
    from botocore.auth import SigV4Auth
    from botocore.client import BaseClient

try:
    import boto3
    from boto3.s3 import inject

    def extract_custom_headers(
        span: "InstanaSpan", headers: Optional[Dict[str, Any]] = None
    ) -> None:
        if not agent.options.extra_http_headers or not headers:
            return
        try:
            for custom_header in agent.options.extra_http_headers:
                if custom_header in headers:
                    span.set_attribute(
                        "http.header.%s" % custom_header, headers[custom_header]
                    )

        except Exception:
            logger.debug("extract_custom_headers: ", exc_info=True)

    def lambda_inject_context(payload: Dict[str, Any], span: "InstanaSpan") -> None:
        """
        When boto3 lambda client 'Invoke' is called, we want to inject the tracing context.
        boto3/botocore has specific requirements:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.invoke
        """
        try:
            invoke_payload = payload.get("Payload", {})

            if not isinstance(invoke_payload, dict):
                invoke_payload = json.loads(invoke_payload)

            tracer.inject(span.context, Format.HTTP_HEADERS, invoke_payload)
            payload["Payload"] = json.dumps(invoke_payload)
        except Exception:
            logger.debug("non-fatal lambda_inject_context: ", exc_info=True)

    @wrapt.patch_function_wrapper("botocore.auth", "SigV4Auth.add_auth")
    def emit_add_auth_with_instana(
        wrapped: Callable[..., None],
        instance: "SigV4Auth",
        args: Tuple[object],
        kwargs: Dict[str, Any],
    ) -> Callable[..., None]:
        current_span = get_current_span()
        if not tracing_is_off() and current_span and current_span.is_recording():
            extract_custom_headers(current_span, args[0].headers)
        return wrapped(*args, **kwargs)

    @wrapt.patch_function_wrapper("botocore.client", "BaseClient._make_api_call")
    def make_api_call_with_instana(
        wrapped: Callable[..., Dict[str, Any]],
        instance: Type["BaseClient"],
        arg_list: Sequence[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        # If we're not tracing, just return
        if tracing_is_off():
            return wrapped(*arg_list, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()

        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span("boto3", span_context=parent_context) as span:
            try:
                operation = arg_list[0]
                payload = arg_list[1]

                span.set_attribute("op", operation)
                span.set_attribute("ep", instance._endpoint.host)
                span.set_attribute("reg", instance._client_config.region_name)

                span.set_attribute(
                    SpanAttributes.HTTP_URL,
                    instance._endpoint.host + ":443/" + arg_list[0],
                )
                span.set_attribute(SpanAttributes.HTTP_METHOD, "POST")

                # Don't collect payload for SecretsManager
                if not hasattr(instance, "get_secret_value"):
                    span.set_attribute("payload", payload)

                # Inject context when invoking lambdas
                if "lambda" in instance._endpoint.host and operation == "Invoke":
                    lambda_inject_context(payload, span)

            except Exception:
                logger.debug("make_api_call_with_instana: collect error", exc_info=True)

            try:
                result = wrapped(*arg_list, **kwargs)

                if isinstance(result, dict):
                    http_dict = result.get("ResponseMetadata")
                    if isinstance(http_dict, dict):
                        status = http_dict.get("HTTPStatusCode")
                        if status is not None:
                            span.set_attribute("http.status_code", status)
                        headers = http_dict.get("HTTPHeaders")
                        extract_custom_headers(span, headers)

                return result
            except Exception as exc:
                span.mark_as_errored({"error": exc})
                raise

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
