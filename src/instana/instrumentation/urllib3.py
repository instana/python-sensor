# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017


from typing import Dict
import wrapt
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import set_span_in_context

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent
from instana.span import InstanaSpan
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import get_tracer_tuple, tracing_is_off

try:
    import urllib3

    def _extract_custom_headers(span: InstanaSpan, headers: Dict) -> None:
        if agent.options.extra_http_headers is None:
            return

        try:
            for custom_header in agent.options.extra_http_headers:
                if custom_header in headers:
                    span.set_attribute(f"http.header.{custom_header}", headers[custom_header])
        except Exception:
            logger.debug("urllib3 _extract_custom_headers error: ", exc_info=True)

    def _collect_kvs(instance, args, kwargs) -> Dict:
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
            logger.debug("urllib3 _collect_kvs error: ", exc_info=True)
            return kvs
        else:
            return kvs

    def collect_response(span, response):
        try:
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status)

            _extract_custom_headers(span, response.headers)

            if 500 <= response.status:
                span.mark_as_errored()
        except Exception:
            logger.debug("urllib3 collect_response error: ", exc_info=True)


    @wrapt.patch_function_wrapper('urllib3', 'HTTPConnectionPool.urlopen')
    def urlopen_with_instana(wrapped, instance, args, kwargs):
        tracer, parent_span, span_name = get_tracer_tuple()

        # If we're not tracing, just return; boto3 has it's own visibility
        if tracing_is_off() or (span_name == 'boto3'):
            return wrapped(*args, **kwargs)

        parent_context = set_span_in_context(parent_span)
        
        with tracer.start_as_current_span("urllib3", context=parent_context) as span:
            try:
                kvs = _collect_kvs(instance, args, kwargs)
                if 'url' in kvs:
                    span.set_attribute(SpanAttributes.HTTP_URL, kvs['url'])
                if 'query' in kvs:
                    span.set_attribute("http.params", kvs['query'])
                if 'method' in kvs:
                    span.set_attribute(SpanAttributes.HTTP_METHOD, kvs['method'])
                if 'headers' in kwargs:
                    _extract_custom_headers(span, kwargs['headers'])
                    tracer.inject(span.context, Format.HTTP_HEADERS, kwargs['headers'])

                response = wrapped(*args, **kwargs)

                collect_response(span, response)

                return response
            except Exception as e:
                span.record_exception({'message': e})
                raise

    logger.debug("Instrumenting urllib3")
except ImportError:
    pass
