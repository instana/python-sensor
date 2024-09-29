# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018


from typing import Any, Callable, Dict, Tuple
import wrapt

from instana.log import logger
from instana.span.span import InstanaSpan
from instana.util.traceutils import get_tracer_tuple, tracing_is_off

try:
    import redis

    EXCLUDED_PARENT_SPANS = ["redis", "celery-client", "celery-worker"]

    def collect_attributes(
        span: InstanaSpan,
        instance: redis.client.Redis,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> None:
        try:
            ckw = instance.connection_pool.connection_kwargs

            span.set_attribute("driver", "redis-py")

            host = ckw.get("host", None)
            port = ckw.get("port", "6379")
            db = ckw.get("db", None)

            if host:
                url = f"redis://{host}:{port}"
                if db is not None:
                    url = f"{url}/{db}"
                span.set_attribute("connection", url)
        except Exception:
            logger.debug("redis.collect_attributes non-fatal error", exc_info=True)

    def execute_command_with_instana(
        wrapped: Callable[..., object],
        instance: redis.client.Redis,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        tracer, parent_span, operation_name = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        # If we're not tracing, just return
        if tracing_is_off() or (operation_name in EXCLUDED_PARENT_SPANS):
            return wrapped(*args, **kwargs)

        with tracer.start_as_current_span("redis", span_context=parent_context) as span:
            try:
                collect_attributes(span, instance, args, kwargs)
                if len(args) > 0:
                    span.set_attribute("command", args[0])

                rv = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
                raise
            else:
                return rv

    def execute_with_instana(
        wrapped: Callable[..., object],
        instance: redis.client.Redis,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        tracer, parent_span, operation_name = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        # If we're not tracing, just return
        if tracing_is_off() or (operation_name in EXCLUDED_PARENT_SPANS):
            return wrapped(*args, **kwargs)

        with tracer.start_as_current_span("redis", span_context=parent_context) as span:
            try:
                collect_attributes(span, instance, args, kwargs)
                span.set_attribute("command", "PIPELINE")

                pipe_cmds = []
                for e in instance.command_stack:
                    pipe_cmds.append(e[0][0])
                span.set_attribute("subCommands", pipe_cmds)
            except Exception as e:
                # If anything breaks during K/V collection, just log a debug message
                logger.debug("Error collecting pipeline commands", exc_info=True)

            try:
                rv = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return rv

    if redis.VERSION < (3, 0, 0):
        wrapt.wrap_function_wrapper(
            "redis.client", "BasePipeline.execute", execute_with_instana
        )
        wrapt.wrap_function_wrapper(
            "redis.client", "StrictRedis.execute_command", execute_command_with_instana
        )
    else:
        wrapt.wrap_function_wrapper(
            "redis.client", "Pipeline.execute", execute_with_instana
        )
        wrapt.wrap_function_wrapper(
            "redis.client", "Redis.execute_command", execute_command_with_instana
        )

        logger.debug("Instrumenting redis")
except ImportError:
    pass
