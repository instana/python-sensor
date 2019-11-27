"""
couchbase instrumentation - This instrumentation supports the Python CouchBase 2.5 SDK only currently:
https://docs.couchbase.com/python-sdk/2.5/start-using-sdk.html
"""
from __future__ import absolute_import

import wrapt
import opentracing

from ..log import logger
from ..singletons import tracer

try:
    import couchbase

    def make_wrapper(op):
        def wrapper(wrapped, instance, args, kwargs):
            parent_span = tracer.active_span

            # If we're not tracing, just return
            if parent_span is None:
                return wrapped(*args, **kwargs)

            with tracer.start_active_span("couchbase", child_of=parent_span) as scope:
                try:
                    scope.span.set_tag('couchbase.hostname', instance.server_nodes[0])
                    scope.span.set_tag('couchbase.bucket', instance.bucket)
                    scope.span.set_tag('couchbase.type', op)
                    return wrapped(*args, **kwargs)
                except Exception as e:
                    scope.span.log_exception(e)
                    scope.span.set_tag('couchbase.error', repr(e))
                    raise
        return wrapper

    # List of operations to instrument
    # incr, incr_multi, decr, decr_multi, retrieve_in are wrappers around operations above
    operations = ['upsert', 'insert', 'replace', 'append', 'prepend', 'get', 'rget',
                  'touch', 'lock', 'unlock', 'remove', 'counter', 'mutate_in', 'lookup_in',
                  'stats', 'ping', 'diagnostics', 'observe',

                  'upsert_multi', 'insert_multi', 'replace_multi', 'append_multi',
                  'prepend_multi', 'get_multi', 'touch_multi', 'lock_multi', 'unlock_multi',
                  'observe_multi', 'endure_multi', 'remove_multi', 'counter_multi']

    def query_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*args, **kwargs)

        with tracer.start_active_span("couchbase", child_of=parent_span) as scope:
            try:
                scope.span.set_tag('couchbase.hostname', instance.server_nodes[0])
                scope.span.set_tag('couchbase.bucket', instance.bucket)
                scope.span.set_tag('couchbase.type', 'n1ql_query')
                scope.span.set_tag('couchbase.q', args[0])
                return wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                scope.span.set_tag('couchbase.error', repr(e))
                raise

    for op in operations:
        f = make_wrapper(op)
        wrapt.wrap_function_wrapper('couchbase.bucket', 'Bucket.%s' % op, f)

    wrapt.wrap_function_wrapper('couchbase.bucket', 'Bucket.n1ql_query', query_with_instana)

    logger.debug("Instrumenting couchbase")
except ImportError:
    pass