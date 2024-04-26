# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

"""
couchbase instrumentation - This instrumentation supports the Python CouchBase 2.3.4 --> 2.5.x SDK currently:
https://docs.couchbase.com/python-sdk/2.5/start-using-sdk.html
"""

import wrapt

from ..log import logger
from ..util.traceutils import get_tracer_tuple, tracing_is_off

try:
    import couchbase

    if not (hasattr(couchbase, '__version__') and couchbase.__version__[0] == '2'
            and (couchbase.__version__[2] > '3'
                 or (couchbase.__version__[2] == '3' and couchbase.__version__[4] >= '4'))
        ):
        logger.debug("Instana supports 2.3.4 <= couchbase_versions < 3.0.0. Skipping.")
        raise ImportError

    from couchbase.n1ql import N1QLQuery

    # List of operations to instrument
    # incr, incr_multi, decr, decr_multi, retrieve_in are wrappers around operations above
    operations = ['upsert', 'insert', 'replace', 'append', 'prepend', 'get', 'rget',
                  'touch', 'lock', 'unlock', 'remove', 'counter', 'mutate_in', 'lookup_in',
                  'stats', 'ping', 'diagnostics', 'observe',

                  'upsert_multi', 'insert_multi', 'replace_multi', 'append_multi',
                  'prepend_multi', 'get_multi', 'touch_multi', 'lock_multi', 'unlock_multi',
                  'observe_multi', 'endure_multi', 'remove_multi', 'counter_multi']

    def capture_kvs(scope, instance, query_arg, op):
        try:
            scope.span.set_tag('couchbase.hostname', instance.server_nodes[0])
            scope.span.set_tag('couchbase.bucket', instance.bucket)
            scope.span.set_tag('couchbase.type', op)

            if query_arg is not None:
                query = None
                if type(query_arg) is N1QLQuery:
                    query = query_arg.statement
                else:
                    query = query_arg

                scope.span.set_tag('couchbase.sql', query)
        except:
            # No fail on key capture - best effort
            pass

    def make_wrapper(op):
        def wrapper(wrapped, instance, args, kwargs):
            tracer, parent_span, _ = get_tracer_tuple()

            # If we're not tracing, just return
            if tracing_is_off():
                return wrapped(*args, **kwargs)

            with tracer.start_active_span("couchbase", child_of=parent_span) as scope:
                capture_kvs(scope, instance, None, op)
                try:
                    return wrapped(*args, **kwargs)
                except Exception as e:
                    scope.span.log_exception(e)
                    scope.span.set_tag('couchbase.error', repr(e))
                    raise
        return wrapper

    def query_with_instana(wrapped, instance, args, kwargs):
        tracer, parent_span, _ = get_tracer_tuple()

        # If we're not tracing, just return
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        with tracer.start_active_span("couchbase", child_of=parent_span) as scope:
            capture_kvs(scope, instance, args[0], 'n1ql_query')
            try:
                return wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                scope.span.set_tag('couchbase.error', repr(e))
                raise

    logger.debug("Instrumenting couchbase")
    wrapt.wrap_function_wrapper('couchbase.bucket', 'Bucket.n1ql_query', query_with_instana)
    for op in operations:
        f = make_wrapper(op)
        wrapt.wrap_function_wrapper('couchbase.bucket', 'Bucket.%s' % op, f)

except ImportError:
    pass
