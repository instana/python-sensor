# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import json
import wrapt
import inspect

from ..log import logger
from ..singletons import tracer


try:
    import boto3
    from boto3.s3 import inject

    def lambda_inject_context(payload, scope):
        """
        When boto3 lambda client 'Invoke' is called, we want to inject the tracing context.
        boto3/botocore has specific requirements:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.invoke
        """
        try:
            invoke_payload = payload.get('Payload', {})

            if not isinstance(invoke_payload, dict):
                invoke_payload = json.loads(invoke_payload)

            tracer.inject(scope.span.context, 'http_headers', invoke_payload)
            payload['Payload'] = json.dumps(invoke_payload)
        except Exception:
            logger.debug("non-fatal lambda_inject_context: ", exc_info=True)


    @wrapt.patch_function_wrapper('botocore.client', 'BaseClient._make_api_call')
    def make_api_call_with_instana(wrapped, instance, arg_list, kwargs):
        # pylint: disable=protected-access
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*arg_list, **kwargs)

        with tracer.start_active_span("boto3", child_of=parent_span) as scope:
            try:
                operation = arg_list[0]
                payload = arg_list[1]

                scope.span.set_tag('op', operation)
                scope.span.set_tag('ep', instance._endpoint.host)
                scope.span.set_tag('reg', instance._client_config.region_name)

                scope.span.set_tag('http.url', instance._endpoint.host + ':443/' + arg_list[0])
                scope.span.set_tag('http.method', 'POST')

                # Don't collect payload for SecretsManager
                if not hasattr(instance, 'get_secret_value'):
                    scope.span.set_tag('payload', payload)

                # Inject context when invoking lambdas
                if 'lambda' in instance._endpoint.host and operation == 'Invoke':
                    lambda_inject_context(payload, scope)


            except Exception as exc:
                logger.debug("make_api_call_with_instana: collect error", exc_info=True)

            try:
                result = wrapped(*arg_list, **kwargs)

                if isinstance(result, dict):
                    http_dict = result.get('ResponseMetadata')
                    if isinstance(http_dict, dict):
                        status = http_dict.get('HTTPStatusCode')
                        if status is not None:
                            scope.span.set_tag('http.status_code', status)

                return result
            except Exception as exc:
                scope.span.mark_as_errored({'error': exc})
                raise

    def s3_inject_method_with_instana(wrapped, instance, arg_list, kwargs):
        fas = inspect.getfullargspec(wrapped)
        fas_args = fas.args
        fas_args.remove('self')

        # pylint: disable=protected-access
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*arg_list, **kwargs)

        with tracer.start_active_span("boto3", child_of=parent_span) as scope:
            try:
                operation = wrapped.__name__
                scope.span.set_tag('op', operation)
                scope.span.set_tag('ep', instance._endpoint.host)
                scope.span.set_tag('reg', instance._client_config.region_name)

                scope.span.set_tag('http.url', instance._endpoint.host + ':443/' + operation)
                scope.span.set_tag('http.method', 'POST')

                arg_length = len(arg_list)
                if arg_length > 0:
                    payload = {}
                    for index in range(arg_length):
                        if fas_args[index] in ['Filename', 'Bucket', 'Key']:
                            payload[fas_args[index]] = arg_list[index]
                    scope.span.set_tag('payload', payload)
            except Exception as exc:
                logger.debug("s3_inject_method_with_instana: collect error", exc_info=True)

            try:
                return wrapped(*arg_list, **kwargs)
            except Exception as exc:
                scope.span.mark_as_errored({'error': exc})
                raise

    for method in ['upload_file', 'upload_fileobj', 'download_file', 'download_fileobj']:
        wrapt.wrap_function_wrapper('boto3.s3.inject', method, s3_inject_method_with_instana)

    logger.debug("Instrumenting boto3")
except ImportError:
    pass
