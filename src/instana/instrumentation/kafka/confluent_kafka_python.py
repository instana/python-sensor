# (c) Copyright IBM Corp. 2025

try:
    from typing import Any, Callable, Dict, List, Optional, Tuple

    import confluent_kafka  # noqa: F401
    import wrapt
    from opentelemetry.trace import SpanKind

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.util.traceutils import (
        get_tracer_tuple,
        tracing_is_off,
    )

    @wrapt.patch_function_wrapper("confluent_kafka", "Producer.produce")
    def trace_kafka_produce(
        wrapped: Callable[..., "confluent_kafka.Producer.produce"],
        instance: "confluent_kafka.Producer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> None:
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span(
            "kafka-producer", span_context=parent_context, kind=SpanKind.PRODUCER
        ) as span:
            span.set_attribute("kafka.service", args[0])
            span.set_attribute("kafka.access", "send")

            # context propagation
            tracer.inject(
                span.context,
                Format.KAFKA_HEADERS,
                kwargs.get("headers", {}),
                disable_w3c_trace_context=True,
            )

            try:
                res = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return res

    @wrapt.patch_function_wrapper("confluent_kafka", "Consumer.consume")
    def trace_kafka_consume(
        wrapped: Callable[..., "confluent_kafka.Consumer.consume"],
        instance: "confluent_kafka.Consumer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> List[confluent_kafka.Message]:
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()

        parent_context = (
            parent_span.get_span_context()
            if parent_span
            else tracer.extract(
                Format.KAFKA_HEADERS, {}, disable_w3c_trace_context=True
            )
        )

        with tracer.start_as_current_span(
            "kafka-consumer", span_context=parent_context, kind=SpanKind.CONSUMER
        ) as span:
            topic = list(instance.subscription())[0]
            span.set_attribute("kafka.service", topic)
            span.set_attribute("kafka.access", "consume")

            try:
                res = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return res

    @wrapt.patch_function_wrapper("confluent_kafka", "Consumer.poll")
    def trace_kafka_poll(
        wrapped: Callable[..., "confluent_kafka.Consumer.poll"],
        instance: "confluent_kafka.Consumer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> Optional[confluent_kafka.Message]:
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()

        parent_context = (
            parent_span.get_span_context()
            if parent_span
            else tracer.extract(
                Format.KAFKA_HEADERS, {}, disable_w3c_trace_context=True
            )
        )

        with tracer.start_as_current_span(
            "kafka-consumer", span_context=parent_context, kind=SpanKind.CONSUMER
        ) as span:
            topic = list(instance.subscription())[0]
            span.set_attribute("kafka.service", topic)
            span.set_attribute("kafka.access", "poll")

            try:
                res = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return res

    logger.debug("Instrumenting Kafka (confluent_kafka)")
except ImportError:
    pass
