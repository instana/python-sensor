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

    operations = ['upsert', 'insert', 'replace', 'append', 'prepend', 'get', 'touch', 'lock',
                  'unlock', 'remove', 'counter', 'mutate_in', 'lookup_in', 'retrieve_in', 'incr',
                  'incr_multi', 'decr', 'decr_multi', 'stats', 'ping', 'diagnostics', 'observe',
                  'endure', 'durability', 'upsert_multi', 'insert_multi', 'replace_multi', 'append_multi',
                  'prepend_multi', 'get_multi', 'touch_multi', 'lock_multi', 'unlock_multi', 'observe_multi',
                  'endure_multi', 'remove_multi', 'counter_multi', 'rget', 'rget_multi']

    for op in operations:
        f = make_wrapper(op)
        wrapt.wrap_function_wrapper('couchbase.bucket', 'Bucket.%s' % op, f)

    logger.debug("Instrumenting couchbase")
except ImportError:
    pass