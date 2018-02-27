from __future__ import absolute_import
import instana
from instana.log import logger
import opentracing
import opentracing.ext.tags as ext
import wrapt


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
                kvs['method'] = kwargs['method']
                kvs['path'] = kwargs['url']

            if type(instance) is urllib3.connectionpool.HTTPSConnectionPool:
                kvs['url'] = 'https://%s:%d%s' % (kvs['host'], kvs['port'], kvs['path'])
            else:
                kvs['url'] = 'http://%s:%d%s' % (kvs['host'], kvs['port'], kvs['path'])
        except Exception as e:
            logger.debug(e)
            return kvs
        else:
            return kvs

    @wrapt.patch_function_wrapper('urllib3', 'HTTPConnectionPool.urlopen')
    def urlopen_with_instana(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()

        # If we're not tracing, just return
        if context is None:
            return wrapped(*args, **kwargs)

        try:
            span = instana.internal_tracer.start_span("urllib3", child_of=context)

            kvs = collect(instance, args, kwargs)
            if 'url' in kvs:
                span.set_tag(ext.HTTP_URL, kvs['url'])
            if 'method' in kvs:
                span.set_tag(ext.HTTP_METHOD, kvs['method'])

            instana.internal_tracer.inject(span.context, opentracing.Format.HTTP_HEADERS, kwargs["headers"])
            rv = wrapped(*args, **kwargs)

            span.set_tag(ext.HTTP_STATUS_CODE, rv.status)
            if 500 <= rv.status <= 599:
                span.set_tag("error", True)
                ec = span.tags.get('ec', 0)
                span.set_tag("ec", ec+1)

        except Exception as e:
            span.log_kv({'message': e})
            span.set_tag("error", True)
            ec = span.tags.get('ec', 0)
            span.set_tag("ec", ec+1)
            span.finish()
            raise
        else:
            span.finish()
            return rv

    instana.log.debug("Instrumenting urllib3")
except ImportError:
    pass
