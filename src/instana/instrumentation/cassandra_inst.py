# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
cassandra instrumentation
https://docs.datastax.com/en/developer/python-driver/3.20/
https://github.com/datastax/python-driver
"""
import wrapt
from ..log import logger
from ..util.traceutils import get_tracer_tuple, tracing_is_off

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
        span.mark_as_errored({"cassandra.error": results.summary})
        span.finish()


    def request_init_with_instana(fn):
        tracer, parent_span, _ = get_tracer_tuple()

        if tracing_is_off():
            return

        ctags = {}
        if isinstance(fn.query, cassandra.query.SimpleStatement):
            ctags["cassandra.query"] = fn.query.query_string
        elif isinstance(fn.query, cassandra.query.BoundStatement):
            ctags["cassandra.query"] = fn.query.prepared_statement.query_string

        ctags["cassandra.keyspace"] = fn.session.keyspace
        ctags["cassandra.cluster"] = fn.session.cluster.metadata.cluster_name

        with tracer.start_active_span("cassandra", child_of=parent_span,
                                      tags=ctags, finish_on_close=False) as scope:
            fn.add_callback(cb_request_finish, scope.span, fn)
            fn.add_errback(cb_request_error, scope.span, fn)


    @wrapt.patch_function_wrapper('cassandra.cluster', 'Session.__init__')
    def init_with_instana(wrapped, instance, args, kwargs):
        session = wrapped(*args, **kwargs)
        instance.add_request_init_listener(request_init_with_instana)
        return session


    logger.debug("Instrumenting cassandra")

except ImportError:
    pass
