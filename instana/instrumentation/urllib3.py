from __future__ import absolute_import

import opentracing
import opentracing.ext.tags as ext
import wrapt

from ..log import logger
from ..singletons import agent, tracer
from ..util import strip_secrets

try:
    import urllib3 # noqa

    def collect(instance, args, kwargs):
        """ Build and return a fully qualified URL for this request """
        try:
            kvs = {}
            kvs['host'] = instance.host
            kvs['port'] = instance.port

            if args is not None and len(args) is 2:
                kvs['method'] = args[0]
                kvs['path'] = args[1]
            else:
                kvs['method'] = kwargs.get('method')
                kvs['path'] = kwargs.get('path')
                if kvs['path'] is None:
                    kvs['path'] = kwargs.get('url')

            # Strip any secrets from potential query params
            if '?' in kvs['path']:
                parts = kvs['path'].split('?')
                kvs['path'] = parts[0]
                if len(parts) is 2:
                    kvs['query'] = strip_secrets(parts[1], agent.secrets_matcher, agent.secrets_list)

            if type(instance) is urllib3.connectionpool.HTTPSConnectionPool:
                kvs['url'] = 'https://%s:%d%s' % (kvs['host'], kvs['port'], kvs['path'])
            else:
                kvs['url'] = 'http://%s:%d%s' % (kvs['host'], kvs['port'], kvs['path'])
        except Exception:
            logger.debug("urllib3 collect error", exc_info=True)
            return kvs
        else:
            return kvs

    @wrapt.patch_function_wrapper('urllib3', 'HTTPConnectionPool.urlopen')
    def urlopen_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
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

                rv = wrapped(*args, **kwargs)

                scope.span.set_tag(ext.HTTP_STATUS_CODE, rv.status)
                if 500 <= rv.status <= 599:
                    scope.span.set_tag("error", True)
                    ec = scope.span.tags.get('ec', 0)
                    scope.span.set_tag("ec", ec+1)

                return rv
            except Exception as e:
                scope.span.log_kv({'message': e})
                scope.span.set_tag("error", True)
                ec = scope.span.tags.get('ec', 0)
                scope.span.set_tag("ec", ec+1)
                raise

    logger.debug("Instrumenting urllib3")
except ImportError:
    pass
