from __future__ import absolute_import

import opentracing
import opentracing.ext.tags as ext
import wrapt

from ..log import logger
from ..singletons import agent, tracer
from ..util import strip_secrets_from_query

try:
    import urllib3

    def collect(instance, args, kwargs):
        """ Build and return a fully qualified URL for this request """
        kvs = dict()
        try:
            kvs['host'] = instance.host
            kvs['port'] = instance.port

            if args is not None and len(args) == 2:
                kvs['method'] = args[0]
                kvs['path'] = args[1]
            else:
                kvs['method'] = kwargs.get('method')
                kvs['path'] = kwargs.get('path')
                if kvs['path'] is None:
                    kvs['path'] = kwargs.get('url')

            # Strip any secrets from potential query params
            if kvs.get('path') is not None and ('?' in kvs['path']):
                parts = kvs['path'].split('?')
                kvs['path'] = parts[0]
                if len(parts) == 2:
                    kvs['query'] = strip_secrets_from_query(parts[1], agent.options.secrets_matcher, agent.options.secrets_list)

            if type(instance) is urllib3.connectionpool.HTTPSConnectionPool:
                kvs['url'] = 'https://%s:%d%s' % (kvs['host'], kvs['port'], kvs['path'])
            else:
                kvs['url'] = 'http://%s:%d%s' % (kvs['host'], kvs['port'], kvs['path'])
        except Exception:
            logger.debug("urllib3 collect error", exc_info=True)
            return kvs
        else:
            return kvs

    def collect_response(scope, response):
        try:
            scope.span.set_tag(ext.HTTP_STATUS_CODE, response.status)

            if agent.options.extra_http_headers is not None:
                for custom_header in agent.options.extra_http_headers:
                    if custom_header in response.headers:
                        scope.span.set_tag("http.%s" % custom_header, response.headers[custom_header])

            if 500 <= response.status <= 599:
                scope.span.mark_as_errored()
        except Exception:
            logger.debug("collect_response", exc_info=True)

    @wrapt.patch_function_wrapper('urllib3', 'HTTPConnectionPool.urlopen')
    def urlopen_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return; boto3 has it's own visibility
        if parent_span is None or parent_span.operation_name == 'boto3':
            return wrapped(*args, **kwargs)

        with tracer.start_active_span("urllib3", child_of=parent_span) as scope:
            try:
                kvs = collect(instance, args, kwargs)
                if 'url' in kvs:
                    scope.span.set_tag(ext.HTTP_URL, kvs['url'])
                if 'query' in kvs:
                    scope.span.set_tag("http.params", kvs['query'])
                if 'method' in kvs:
                    scope.span.set_tag(ext.HTTP_METHOD, kvs['method'])

                if 'headers' in kwargs:
                    tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, kwargs['headers'])

                response = wrapped(*args, **kwargs)

                collect_response(scope, response)

                return response
            except Exception as e:
                scope.span.mark_as_errored({'message': e})
                raise

    logger.debug("Instrumenting urllib3")
except ImportError:
    pass
