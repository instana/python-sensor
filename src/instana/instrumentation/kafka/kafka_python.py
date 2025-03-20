# (c) Copyright IBM Corp. 2025

try:
    from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple

    import kafka  # noqa: F401
    import wrapt
    from opentelemetry.trace import SpanKind

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.util.traceutils import (
        get_tracer_tuple,
        tracing_is_off,
    )

    if TYPE_CHECKING:
        from kafka.producer.future import FutureRecordMetadata

    @wrapt.patch_function_wrapper("kafka", "KafkaProducer.send")
    def trace_kafka_send(
        wrapped: Callable[..., "kafka.KafkaProducer.send"],
        instance: "kafka.KafkaProducer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> "FutureRecordMetadata":
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

    @wrapt.patch_function_wrapper("kafka", "KafkaConsumer.__next__")
    def trace_kafka_consume(
        wrapped: Callable[..., "kafka.KafkaConsumer.__next__"],
        instance: "kafka.KafkaConsumer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> "FutureRecordMetadata":
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

    @wrapt.patch_function_wrapper("kafka", "KafkaConsumer.poll")
    def trace_kafka_poll(
        wrapped: Callable[..., "kafka.KafkaConsumer.poll"],
        instance: "kafka.KafkaConsumer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()

        # The KafkaConsumer.consume() from the kafka-python-ng call the
        # KafkaConsumer.poll() internally, so we do not consider it here.
        if parent_span and parent_span.name == "kafka-consumer":
            return wrapped(*args, **kwargs)

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

    logger.debug("Instrumenting Kafka (kafka-python)")
except ImportError:
    pass
