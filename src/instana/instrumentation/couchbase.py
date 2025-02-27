# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

"""
couchbase instrumentation - This instrumentation supports the Python CouchBase 2.3.4 --> 2.5.x SDK currently:
https://docs.couchbase.com/python-sdk/2.5/start-using-sdk.html
"""

try:
    import couchbase
    from instana.log import logger

    if not (
        hasattr(couchbase, "__version__")
        and (couchbase.__version__ >= "2.3.4" and couchbase.__version__ < "3.0.0")
    ):
        logger.debug("Instana supports 2.3.4 <= couchbase_versions < 3.0.0. Skipping.")
        raise ImportError

    from couchbase.bucket import Bucket
    from couchbase.n1ql import N1QLQuery

    from typing import Any, Callable, Dict, Tuple, Union

    import wrapt

    from instana.span.span import InstanaSpan
    from instana.util.traceutils import get_tracer_tuple, tracing_is_off

    # List of operations to instrument
    # incr, incr_multi, decr, decr_multi, retrieve_in are wrappers around operations above
    operations = [
        "upsert",
        "insert",
        "replace",
        "append",
        "prepend",
        "get",
        "rget",
        "touch",
        "lock",
        "unlock",
        "remove",
        "counter",
        "mutate_in",
        "lookup_in",
        "stats",
        "ping",
        "diagnostics",
        "observe",
        "upsert_multi",
        "insert_multi",
        "replace_multi",
        "append_multi",
        "prepend_multi",
        "get_multi",
        "touch_multi",
        "lock_multi",
        "unlock_multi",
        "observe_multi",
        "endure_multi",
        "remove_multi",
        "counter_multi",
    ]

    def collect_attributes(
        span: InstanaSpan,
        instance: Bucket,
        query_arg: Union[N1QLQuery, object],
        op: str,
    ) -> None:
        try:
            span.set_attribute("couchbase.hostname", instance.server_nodes[0])
            span.set_attribute("couchbase.bucket", instance.bucket)
            span.set_attribute("couchbase.type", op)

            if query_arg:
                query = None
                if type(query_arg) is N1QLQuery:
                    query = query_arg.statement
                else:
                    query = query_arg

                span.set_attribute("couchbase.sql", query)
        except Exception:
            # No fail on key capture - best effort
            pass

    def make_wrapper(op: str) -> Callable:
        def wrapper(
            wrapped: Callable[..., object],
            instance: couchbase.bucket.Bucket,
            args: Tuple[object, ...],
            kwargs: Dict[str, Any],
        ) -> object:
            tracer, parent_span, _ = get_tracer_tuple()
            parent_context = parent_span.get_span_context() if parent_span else None

            # If we're not tracing, just return
            if tracing_is_off():
                return wrapped(*args, **kwargs)

            with tracer.start_as_current_span(
                "couchbase", span_context=parent_context
            ) as span:
                collect_attributes(span, instance, None, op)
                try:
                    return wrapped(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_attribute("couchbase.error", repr(exc))
                    logger.debug("Instana couchbase @ wrapper", exc_info=True)

        return wrapper

    def query_with_instana(
        wrapped: Callable[..., object],
        instance: couchbase.bucket.Bucket,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        # If we're not tracing, just return
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        with tracer.start_as_current_span(
            "couchbase", span_context=parent_context
        ) as span:
            try:
                collect_attributes(span, instance, args[0], "n1ql_query")
                return wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("couchbase.error", repr(exc))
                logger.debug("Instana couchbase @ query_with_instana", exc_info=True)

    logger.debug("Instrumenting couchbase")
    wrapt.wrap_function_wrapper(
        "couchbase.bucket", "Bucket.n1ql_query", query_with_instana
    )
    for op in operations:
        f = make_wrapper(op)
        wrapt.wrap_function_wrapper("couchbase.bucket", f"Bucket.{op}", f)

except ImportError:
    pass
