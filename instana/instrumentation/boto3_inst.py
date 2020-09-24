from __future__ import absolute_import

import wrapt
import inspect

from ..log import logger
from ..singletons import tracer


try:
    import boto3
    from boto3.s3 import inject

    @wrapt.patch_function_wrapper('botocore.client', 'BaseClient._make_api_call')
    def make_api_call_with_instana(wrapped, instance, arg_list, kwargs):
        # pylint: disable=protected-access
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*arg_list, **kwargs)

        with tracer.start_active_span("boto3", child_of=parent_span) as scope:
            try:
                scope.span.set_tag('op', arg_list[0])
                scope.span.set_tag('ep', instance._endpoint.host)
                scope.span.set_tag('reg', instance._client_config.region_name)

                scope.span.set_tag('url', instance._endpoint.host + '/')
                scope.span.set_tag('method', 'POST')

                # Don't collect payload for SecretsManager
                if not hasattr(instance, 'get_secret_value'):
                    scope.span.set_tag('payload', arg_list[1])
            except Exception as exc:
                logger.debug("make_api_call_with_instana: collect error", exc_info=True)

            try:
                result = wrapped(*arg_list, **kwargs)

                if isinstance(result, dict):
                    http_dict = result.get('ResponseMetadata')
                    if isinstance(http_dict, dict):
                        status = http_dict.get('HTTPStatusCode')
                        if status is not None:
                            scope.span.set_tag('status', status)

                return result
            except Exception as exc:
                scope.span.mark_as_errored({'message': exc})
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
                scope.span.set_tag('op', wrapped.__name__)
                scope.span.set_tag('ep', instance._endpoint.host)
                scope.span.set_tag('reg', instance._client_config.region_name)

                scope.span.set_tag('url', instance._endpoint.host + '/')
                scope.span.set_tag('method', 'POST')

                index = 1
                payload = {}
                arg_length = len(arg_list)

                for arg_name in fas_args:
                    payload[arg_name] = arg_list[index-1]

                    index += 1
                    if index > arg_length:
                        break

                scope.span.set_tag('payload', payload)
            except Exception as exc:
                logger.debug("s3_inject_method_with_instana: collect error", exc_info=True)

            try:
                return wrapped(*arg_list, **kwargs)
            except Exception as exc:
                scope.span.mark_as_errored({'message': exc})
                raise

    for method in ['upload_file', 'upload_fileobj', 'download_file', 'download_fileobj']:
        wrapt.wrap_function_wrapper('boto3.s3.inject', method, s3_inject_method_with_instana)

    logger.debug("Instrumenting boto3")
except ImportError:
    pass
