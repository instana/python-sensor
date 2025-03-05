# (c) Copyright IBM Corp. 2025
try:
    from typing import TYPE_CHECKING, Any, Callable, Dict, Sequence, Tuple, Type

    from opentelemetry.semconv.trace import SpanAttributes

    from instana.instrumentation.aws.dynamodb import create_dynamodb_span
    from instana.instrumentation.aws.s3 import create_s3_span

    if TYPE_CHECKING:
        from botocore.auth import SigV4Auth
        from botocore.client import BaseClient

        from instana.span.span import InstanaSpan

    import json

    import wrapt

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import tracer
    from instana.span.span import get_current_span
    from instana.util.traceutils import (
        extract_custom_headers,
        get_tracer_tuple,
        tracing_is_off,
    )

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
        args: Sequence[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        # If we're not tracing, just return
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()

        parent_context = parent_span.get_span_context() if parent_span else None

        if instance.meta.service_model.service_name == "dynamodb":
            create_dynamodb_span(wrapped, instance, args, kwargs, parent_context)
        elif instance.meta.service_model.service_name == "s3":
            create_s3_span(wrapped, instance, args, kwargs, parent_context)
        else:
            with tracer.start_as_current_span(
                "boto3", span_context=parent_context
            ) as span:
                operation = args[0]
                payload = args[1]

                span.set_attribute("op", operation)
                span.set_attribute("ep", instance._endpoint.host)
                span.set_attribute("reg", instance._client_config.region_name)

                span.set_attribute(
                    SpanAttributes.HTTP_URL,
                    instance._endpoint.host + ":443/" + args[0],
                )
                span.set_attribute(SpanAttributes.HTTP_METHOD, "POST")

                # Don't collect payload for SecretsManager
                if not hasattr(instance, "get_secret_value"):
                    span.set_attribute("payload", payload)

                # Inject context when invoking lambdas
                if "lambda" in instance._endpoint.host and operation == "Invoke":
                    lambda_inject_context(payload, span)

                try:
                    result = wrapped(*args, **kwargs)

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
        return wrapped(*args, **kwargs)

except ImportError:
    pass
