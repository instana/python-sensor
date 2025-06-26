# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
cassandra instrumentation
https://docs.datastax.com/en/developer/python-driver/3.20/
https://github.com/datastax/python-driver
"""

try:
    from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple

    import cassandra
    import wrapt

    from instana.log import logger
    from instana.util.traceutils import get_tracer_tuple, tracing_is_off

    if TYPE_CHECKING:
        from cassandra.cluster import ResponseFuture, Session

        from instana.span.span import InstanaSpan

    consistency_levels = dict(
        {
            0: "ANY",
            1: "ONE",
            2: "TWO",
            3: "THREE",
            4: "QUORUM",
            5: "ALL",
            6: "LOCAL_QUORUM",
            7: "EACH_QUORUM",
            8: "SERIAL",
            9: "LOCAL_SERIAL",
            10: "LOCAL_ONE",
        }
    )

    def collect_attributes(
        span: "InstanaSpan",
        fn: "ResponseFuture",
    ) -> None:
        tried_hosts = []
        for host in fn.attempted_hosts:
            tried_hosts.append(f"{host.endpoint.address}:{host.endpoint.port}")

        span.set_attribute("cassandra.triedHosts", tried_hosts)
        span.set_attribute("cassandra.coordHost", fn.coordinator_host)

        cl = fn.query.consistency_level
        if cl and cl in consistency_levels:
            span.set_attribute("cassandra.achievedConsistency", consistency_levels[cl])

    def cb_request_finish(
        _,
        span: "InstanaSpan",
        fn: "ResponseFuture",
    ) -> None:
        collect_attributes(span, fn)
        span.end()

    def cb_request_error(
        results: Dict[str, Any],
        span: "InstanaSpan",
        fn: "ResponseFuture",
    ) -> None:
        collect_attributes(span, fn)
        span.mark_as_errored({"cassandra.error": results.summary})
        span.end()

    def request_init_with_instana(
        fn: "ResponseFuture",
    ) -> None:
        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        if tracing_is_off():
            return

        attributes = {}
        if isinstance(fn.query, cassandra.query.SimpleStatement):
            attributes["cassandra.query"] = fn.query.query_string
        elif isinstance(fn.query, cassandra.query.BoundStatement):
            attributes["cassandra.query"] = fn.query.prepared_statement.query_string

        attributes["cassandra.keyspace"] = fn.session.keyspace
        attributes["cassandra.cluster"] = fn.session.cluster.metadata.cluster_name

        with tracer.start_as_current_span(
            "cassandra",
            span_context=parent_context,
            attributes=attributes,
            end_on_exit=False,
        ) as span:
            fn.add_callback(cb_request_finish, span, fn)
            fn.add_errback(cb_request_error, span, fn)

    @wrapt.patch_function_wrapper("cassandra.cluster", "Session.__init__")
    def init_with_instana(
        wrapped: Callable[..., object],
        instance: "Session",
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        session = wrapped(*args, **kwargs)
        instance.add_request_init_listener(request_init_with_instana)
        return session

    logger.debug("Instrumenting cassandra")

except ImportError:
    pass
