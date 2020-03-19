"""
cassandra instrumentation
https://docs.datastax.com/en/developer/python-driver/3.20/
https://github.com/datastax/python-driver
"""
from __future__ import absolute_import

from distutils.version import LooseVersion
import wrapt

from ..log import logger
from ..singletons import tracer

try:
    import cassandra

    consistency_levels = dict({0: "ANY",
                               1: "ONE",
                               2: "TWO",
                               3: "THREE",
                               4: "QUORUM",
                               5: "ALL",
                               6: "LOCAL_QUORUM",
                               7: "EACH_QUORUM",
                               8: "SERIAL",
                               9: "LOCAL_SERIAL",
                               10: "LOCAL_ONE"})

    def collect_response(span, fn):
        tried_hosts = list()
        for host in fn.attempted_hosts:
            tried_hosts.append("%s:%d" % (host.endpoint.address, host.endpoint.port))

        span.set_tag("cassandra.triedHosts", tried_hosts)
        span.set_tag("cassandra.coordHost", fn.coordinator_host)

        cl = fn.query.consistency_level
        if cl and cl in consistency_levels:
            span.set_tag("cassandra.achievedConsistency", consistency_levels[cl])


    def cb_request_finish(results, span, fn):
        collect_response(span, fn)
        span.finish()

    def cb_request_error(results, span, fn):
        collect_response(span, fn)
        span.mark_as_errored({"cassandra.error": results.message})
        span.finish()

    def request_init_with_instana(fn):
        parent_span = tracer.active_span

        if parent_span is not None:
            ctags = dict()
            if isinstance(fn.query, cassandra.query.SimpleStatement):
                ctags["cassandra.query"] = fn.query.query_string
            elif isinstance(fn.query, cassandra.query.BoundStatement):
                ctags["cassandra.query"] = fn.query.prepared_statement.query_string

            ctags["cassandra.keyspace"] = fn.session.keyspace
            ctags["cassandra.cluster"] = fn.session.cluster.metadata.cluster_name

            span = tracer.start_span(
                operation_name="cassandra",
                child_of=parent_span,
                tags=ctags)

            fn.add_callback(cb_request_finish, span, fn)
            fn.add_errback(cb_request_error, span, fn)

    @wrapt.patch_function_wrapper('cassandra.cluster', 'Session.__init__')
    def init_with_instana(wrapped, instance, args, kwargs):
        session =  wrapped(*args, **kwargs)
        instance.add_request_init_listener(request_init_with_instana)
        return session

    logger.debug("Instrumenting cassandra")

except ImportError:
    pass