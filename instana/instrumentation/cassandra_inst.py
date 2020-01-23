"""
cassandra instrumentation
"""
from __future__ import absolute_import

from distutils.version import LooseVersion
import wrapt

from ..log import logger
from ..singletons import tracer

try:
    import cassandra

    def cb_request_finish(results, span):
        logger.debug("cb_request_finish: closing out span")
        span.finish()

    def cb_request_error(results, span):
        logger.debug("cb_request_error: marking span as errored and closing out")

        span.set_tag("error", True)
        ec = span.tags.get('ec', 0)
        span.set_tag("ec", ec + 1)
        span.set_tag("cassandra.error", results.message)
        span.finish()

    def request_init_with_instana(fn):
        logger.debug("request_init_with_instana")

        parent_span = tracer.active_span

        if parent_span is not None:
            logger.debug("We are tracing: starting new cassandra span")

            ctags = dict()
            if isinstance(fn.query, cassandra.query.SimpleStatement):
                ctags["cassandra.query"] = fn.query.query_string
            elif isinstance(fn.query, cassandra.query.BoundStatement):
                ctags["cassandra.query"] = fn.query.prepared_statement.query_string

            ctags["cassandra.keyspace"] = fn.session.keyspace

            # if fn.query.consistency_level:
            #     ctags["cassandra.achievedConsistency"] = fn.query.consistency_level

            span = tracer.start_span(
                operation_name="cassandra",
                child_of=parent_span,
                tags=ctags)

            fn.add_callback(cb_request_finish, span)
            fn.add_errback(cb_request_error, span)
        else:
            logger.debug("We are NOT tracing: not tracing cassandra")


    @wrapt.patch_function_wrapper('cassandra.cluster', 'Session.__init__')
    def init_with_instana(wrapped, instance, args, kwargs):
        session =  wrapped(*args, **kwargs)
        instance.add_request_init_listener(request_init_with_instana)
        return session

    logger.debug("Instrumenting cassandra")

except ImportError:
    pass