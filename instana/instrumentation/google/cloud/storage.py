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
            # Object/blob operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)$'): lambda params, data, match: {
                'gcs.op': params.get('alt', 'json') == 'media' and 'objects.get' or 'objects.attrs',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
            },
            re.compile('^/b/(?P<bucket>[^/]+)/o$'): lambda params, data, match: {
                'gcs.op': 'objects.list',
                'gcs.bucket': unquote(match.group('bucket'))
            },
            # Default object ACLs operations
            re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl/(?P<entity>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'defaultAcls.get',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.entity': unquote(match.group('entity'))
            },
            re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl$'): lambda params, data, match: {
                'gcs.op': 'defaultAcls.list',
                'gcs.bucket': unquote(match.group('bucket')),
            },
            # Object ACL operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl/(?P<entity>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objectAcls.get',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
                'gcs.entity': unquote(match.group('entity'))
            },
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl$'): lambda params, data, match: {
                'gcs.op': 'objectAcls.list',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object'))
            },
            # HMAC keys operations
            re.compile('^/projects/(?P<project>[^/]+)/hmacKeys$'): lambda params, data, match: {
                'gcs.op': 'hmacKeys.list',
                'gcs.projectId': unquote(match.group('project'))
            },
            re.compile('^/projects/(?P<project>[^/]+)/hmacKeys/(?P<accessId>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'hmacKeys.get',
                'gcs.projectId': unquote(match.group('project')),
                'gcs.accessId': unquote(match.group('accessId'))
            },
            # Service account operations
            re.compile('^/projects/(?P<project>[^/]+)/serviceAccount$'): lambda params, data, match: {
                'gcs.op': 'serviceAccount.get',
                'gcs.projectId': unquote(match.group('project'))
            }
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
            # Object/blob operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/compose$'): lambda params, data, match: {
                'gcs.op': 'objects.compose',
                'gcs.destinationBucket': unquote(match.group('bucket')),
                'gcs.destinationObject': unquote(match.group('object')),
                'gcs.sourceObjects': ','.join(
                    ['%s/%s' % (unquote(match.group('bucket')), o.name) for o in data.get('sourceObjects', [])]
                )
            },
            re.compile('^/b/(?P<srcBucket>[^/]+)/o/(?P<srcObject>[^/]+)/copyTo/b/(?P<destBucket>[^/]+)/o/(?P<destObject>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objects.copy',
                'gcs.destinationBucket': unquote(match.group('destBucket')),
                'gcs.destinationObject': unquote(match.group('destObject')),
                'gcs.sourceBucket': unquote(match.group('srcBucket')),
                'gcs.sourceObject': unquote(match.group('srcObject')),
            },
            re.compile('^/b/(?P<bucket>[^/]+)/o$'): lambda params, data, match: {
                'gcs.op': 'objects.insert',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': params.get('name', data.get('name', None)),
            },
            re.compile('^/b/(?P<srcBucket>[^/]+)/o/(?P<srcObject>[^/]+)/rewriteTo/b/(?P<destBucket>[^/]+)/o/(?P<destObject>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objects.rewrite',
                'gcs.destinationBucket': unquote(match.group('destBucket')),
                'gcs.destinationObject': unquote(match.group('destObject')),
                'gcs.sourceBucket': unquote(match.group('srcBucket')),
                'gcs.sourceObject': unquote(match.group('srcObject')),
            },
            # Channel operations
            '/channels/stop': lambda params, data: {
                'gcs.op': 'channels.stop',
                'gcs.entity': data.get('id', None)
            },
            # Default object ACLs operations
            re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl$'): lambda params, data, match: {
                'gcs.op': 'defaultAcls.insert',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.entity': data.get('entity', None)
            },
            # Object ACL operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl$'): lambda params, data, match: {
                'gcs.op': 'objectAcls.insert',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
                'gcs.entity': data.get('entity', None)
            },
            # HMAC keys operations
            re.compile('^/projects/(?P<project>[^/]+)/hmacKeys$'): lambda params, data, match: {
                'gcs.op': 'hmacKeys.create',
                'gcs.projectId': unquote(match.group('project'))
            }
        },
        'PATCH': {
            # Bucket operations
            re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'buckets.patch',
                'gcs.bucket': unquote(match.group('bucket')),
            },
            # Object/blob operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objects.patch',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
            },
            # Default object ACLs operations
            re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl/(?P<entity>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'defaultAcls.patch',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.entity': unquote(match.group('entity'))
            },
            # Object ACL operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl/(?P<entity>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objectAcls.patch',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
                'gcs.entity': unquote(match.group('entity'))
            }
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
            # Object/blob operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objects.update',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
            },
            # Default object ACLs operations
            re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl/(?P<entity>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'defaultAcls.update',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.entity': unquote(match.group('entity'))
            },
            # Object ACL operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl/(?P<entity>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objectAcls.update',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
                'gcs.entity': unquote(match.group('entity'))
            },
            # HMAC keys operations
            re.compile('^/projects/(?P<project>[^/]+)/hmacKeys/(?P<accessId>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'hmacKeys.update',
                'gcs.projectId': unquote(match.group('project')),
                'gcs.accessId': unquote(match.group('accessId'))
            }
        },
        'DELETE': {
            # Bucket operations
            re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'buckets.delete',
                'gcs.bucket': unquote(match.group('bucket')),
            },
            # Object/blob operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objects.delete',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
            },
            # Default object ACLs operations
            re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl/(?P<entity>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'defaultAcls.delete',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.entity': unquote(match.group('entity'))
            },
            # Object ACL operations
            re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl/(?P<entity>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'objectAcls.delete',
                'gcs.bucket': unquote(match.group('bucket')),
                'gcs.object': unquote(match.group('object')),
                'gcs.entity': unquote(match.group('entity'))
            },
            # HMAC keys operations
            re.compile('^/projects/(?P<project>[^/]+)/hmacKeys/(?P<accessId>[^/]+)$'): lambda params, data, match: {
                'gcs.op': 'hmacKeys.delete',
                'gcs.projectId': unquote(match.group('project')),
                'gcs.accessId': unquote(match.group('accessId'))
            }
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

    wrapt.wrap_function_wrapper('google.cloud.storage._http', 'Connection.api_request', execute_with_instana)
    wrapt.wrap_function_wrapper('google.cloud.storage.blob', 'Blob._do_download', download_with_instana)
    wrapt.wrap_function_wrapper('google.cloud.storage.blob', 'Blob._do_upload', upload_with_instana)
except ImportError:
    pass
