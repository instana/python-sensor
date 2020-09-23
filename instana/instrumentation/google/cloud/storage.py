from __future__ import absolute_import

import wrapt
import re
from urllib.parse import unquote

from ....log import logger
from ....singletons import tracer

try:
    from google.cloud import storage

    # A map of GCS API param collectors organized as:
    #   request_method -> path_matcher -> collector
    #
    # * request method - the HTTP method used to make an API request (GET, POST, etc.)
    # * path_matcher - either a string or a regex applied to the API request path (string values match first).
    # * collector - a lambda returning a dict of span from  API request query string.
    #               parameters and request body data. If a regex is used as a path matcher, the match result
    #               will be provided as a third argument.
    _storage_api = {
        'GET': {
            # Bucket operations
            '/b': lambda params, data: {
                'gcs.op': 'buckets.list',
                'gcs.projectId': params.get('project', None)
            },
            re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'buckets.get',
                'gcs.bucket': unquote(match.group('bucket')),
            },
            re.compile('^/b/(?P<bucket>[^/]+)/iam$'): lambda params, data, match: {
                'gcs.op': 'buckets.getIamPolicy',
                'gcs.bucket': unquote(match.group('bucket')),
            },
            re.compile('^/b/(?P<bucket>[^/]+)/iam/testPermissions$'): lambda params, data, match: {
                'gcs.op': 'buckets.testIamPermissions',
                'gcs.bucket': unquote(match.group('bucket')),
            },
        },
        'POST': {
            # Bucket operations
            '/b': lambda params, data: {
                'gcs.op': 'buckets.insert',
                'gcs.projectId': params.get('project', None),
                'gcs.bucket': data.get('name', None),
            },
            re.compile('^/b/(?P<bucket>[^/]+)/lockRetentionPolicy$'): lambda params, data, match: {
                'gcs.op': 'buckets.lockRetentionPolicy',
                'gcs.bucket': unquote(match.group('bucket')),
            },
        },
        'PATCH': {
            # Bucket operations
            re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'buckets.patch',
                'gcs.bucket': unquote(match.group('bucket')),
            },
        },
        'PUT': {
            # Bucket operations
            re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'buckets.update',
                'gcs.bucket': unquote(match.group('bucket')),
            },
            re.compile('^/b/(?P<bucket>[^/]+)/iam$'): lambda params, data, match: {
                'gcs.op': 'buckets.setIamPolicy',
                'gcs.bucket': unquote(match.group('bucket')),
            },
        },
        'DELETE': {
            # Bucket operations
            re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'buckets.delete',
                'gcs.bucket': unquote(match.group('bucket')),
            },
        }
    }

    def collect_tags(api_request):
        """
        Extract span tags from Google Cloud Storage API request. Returns None if the request is not
        supported.

        :param: dict
        :return: dict or None
        """
        method, path = api_request.get('method', None), api_request.get('path', None)

        if method not in _storage_api:
            return

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

    def execute_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # return early if we're not tracing
        if parent_span is None:
            return wrapped(*args, **kwargs)

        tags = collect_tags(kwargs)

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

    wrapt.wrap_function_wrapper('google.cloud.storage._http', 'Connection.api_request', execute_with_instana)
except ImportError:
    pass
