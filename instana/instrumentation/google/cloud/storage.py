# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import wrapt
import re

from ....log import logger
from ....singletons import tracer
from .collectors import _storage_api

try:
    from google.cloud import storage

    logger.debug('Instrumenting google-cloud-storage')

    def _collect_tags(api_request):
        """
        Extract span tags from Google Cloud Storage API request. Returns None if the request is not
        supported.

        :param: dict
        :return: dict or None
        """
        method, path = api_request.get('method', None), api_request.get('path', None)

        if method not in _storage_api:
            return

        try:
            params = api_request.get('query_params', {})
            data = api_request.get('data', {})

            if path in _storage_api[method]:
                # check is any of string keys matches the path exactly
                return _storage_api[method][path](params, data)
            else:
                # look for a regex that matches the string
                for (matcher, collect) in _storage_api[method].items():
                    if not isinstance(matcher, re.Pattern):
                        continue

                    m = matcher.match(path)
                    if m is None:
                        continue

                    return collect(params, data, m)
        except Exception:
            logger.debug("instana.instrumentation.google.cloud.storage._collect_tags: ", exc_info=True)

    def execute_with_instana(wrapped, instance, args, kwargs):
        # batch requests are traced with finish_batch_with_instana()
        if isinstance(instance, storage.Batch):
            return wrapped(*args, **kwargs)

        parent_span = tracer.active_span

        # return early if we're not tracing
        if parent_span is None:
            return wrapped(*args, **kwargs)

        tags = _collect_tags(kwargs)

        # don't trace if the call is not instrumented
        if tags is None:
            logger.debug('uninstrumented Google Cloud Storage API request: %s' % kwargs)
            return wrapped(*args, **kwargs)

        with tracer.start_active_span('gcs', child_of=parent_span) as scope:
            for (k, v) in tags.items():
                scope.span.set_tag(k, v)

            try:
                kv = wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return kv

    def download_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # return early if we're not tracing
        if parent_span is None:
            return wrapped(*args, **kwargs)

        with tracer.start_active_span('gcs', child_of=parent_span) as scope:
            scope.span.set_tag('gcs.op', 'objects.get')
            scope.span.set_tag('gcs.bucket', instance.bucket.name)
            scope.span.set_tag('gcs.object', instance.name)

            start = len(args) > 4 and args[4] or kwargs.get('start', None)
            if start is None:
                start = ''

            end = len(args) > 5 and args[5] or kwargs.get('end', None)
            if end is None:
                end = ''

            if start != '' or end != '':
                scope.span.set_tag('gcs.range', '-'.join((start, end)))

            try:
                kv = wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return kv

    def upload_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # return early if we're not tracing
        if parent_span is None:
            return wrapped(*args, **kwargs)

        with tracer.start_active_span('gcs', child_of=parent_span) as scope:
            scope.span.set_tag('gcs.op', 'objects.insert')
            scope.span.set_tag('gcs.bucket', instance.bucket.name)
            scope.span.set_tag('gcs.object', instance.name)

            try:
                kv = wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return kv

    def finish_batch_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # return early if we're not tracing
        if parent_span is None:
            return wrapped(*args, **kwargs)

        with tracer.start_active_span('gcs', child_of=parent_span) as scope:
            scope.span.set_tag('gcs.op', 'batch')
            scope.span.set_tag('gcs.projectId', instance._client.project)
            scope.span.set_tag('gcs.numberOfOperations', len(instance._requests))

            try:
                kv = wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return kv

    wrapt.wrap_function_wrapper('google.cloud.storage._http', 'Connection.api_request', execute_with_instana)
    wrapt.wrap_function_wrapper('google.cloud.storage.blob', 'Blob._do_download', download_with_instana)
    wrapt.wrap_function_wrapper('google.cloud.storage.blob', 'Blob._do_upload', upload_with_instana)
    wrapt.wrap_function_wrapper('google.cloud.storage.batch', 'Batch.finish', finish_batch_with_instana)
except ImportError:
    pass
