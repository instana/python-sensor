# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017


import opentracing
import opentracing.ext.tags as ext
import wrapt

from ..log import logger
from ..singletons import agent
from ..util.traceutils import get_tracer_tuple, tracing_is_off
from ..util.secrets import strip_secrets_from_query

try:
    import urllib3


    def extract_custom_headers(span, headers):
        if agent.options.extra_http_headers is None:
            return
        try:
            for custom_header in agent.options.extra_http_headers:
                if custom_header in headers:
                    span.set_tag("http.header.%s" % custom_header, headers[custom_header])

        except Exception:
            logger.debug("extract_custom_headers: ", exc_info=True)


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
                    kvs['query'] = strip_secrets_from_query(parts[1], agent.options.secrets_matcher,
                                                            agent.options.secrets_list)

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

            extract_custom_headers(scope.span, response.headers)

            if 500 <= response.status:
                scope.span.mark_as_errored()
        except Exception:
            logger.debug("collect_response", exc_info=True)


    @wrapt.patch_function_wrapper('urllib3', 'HTTPConnectionPool.urlopen')
    def urlopen_with_instana(wrapped, instance, args, kwargs):
        tracer, parent_span, operation_name = get_tracer_tuple()
        # If we're not tracing, just return; boto3 has it's own visibility
        if (tracing_is_off() or (operation_name == 'boto3')):
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
                    extract_custom_headers(scope.span, kwargs['headers'])
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
