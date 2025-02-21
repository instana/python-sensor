# (c) Copyright IBM Corp. 2025

try:
    from typing import Any, Callable, Dict, List, Optional, Tuple

    import confluent_kafka  # noqa: F401
    import wrapt
    from confluent_kafka import Consumer, Producer
    from opentelemetry.trace import SpanKind

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.util.traceutils import (
        get_tracer_tuple,
        tracing_is_off,
    )

    # As confluent_kafka is a wrapper around the C-developed librdkafka
    # (provided automatically via binary wheels), we have to create new classes
    # inheriting from the confluent_kafka package with the methods to be
    # monkey-patched.
    class InstanaConfluentKafkaProducer(Producer):
        """
        Wrapper class for confluent_kafka.Producer, which is an Asynchronous Kafka Producer.
        """

        def produce(
            self,
            topic: str,
            *args: object,
            **kwargs: Dict[str, Any],
        ) -> None:
            return super().produce(topic, *args, **kwargs)

    class InstanaConfluentKafkaConsumer(Consumer):
        """
        Wrapper class for confluent_kafka.Consumer, which is a high-level Apache Kafka consumer.
        """

        def consume(
            self, *args: object, **kwargs: Dict[str, Any]
        ) -> List[confluent_kafka.Message]:
            return super().consume(*args, **kwargs)

        def poll(
            self, timeout: Optional[float] = -1
        ) -> Optional[confluent_kafka.Message]:
            return super().poll(timeout)

    def trace_kafka_produce(
        wrapped: Callable[..., InstanaConfluentKafkaProducer.produce],
        instance: InstanaConfluentKafkaProducer,
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
            span.set_attribute("kafka.access", "produce")

            # context propagation
            headers = args[6] if len(args) > 6 else kwargs.get("headers", {})
            tracer.inject(
                span.context,
                Format.KAFKA_HEADERS,
                headers,
                disable_w3c_trace_context=True,
            )

            try:
                res = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return res

    def trace_kafka_consume(
        wrapped: Callable[..., InstanaConfluentKafkaConsumer.consume],
        instance: InstanaConfluentKafkaConsumer,
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
            span.set_attribute("kafka.access", "consume")

            try:
                res = wrapped(*args, **kwargs)
                if isinstance(res, list) and len(res) > 0:
                    span.set_attribute("kafka.service", res[0].topic())
            except Exception as exc:
                span.record_exception(exc)
            else:
                return res

    def trace_kafka_poll(
        wrapped: Callable[..., InstanaConfluentKafkaConsumer.poll],
        instance: InstanaConfluentKafkaConsumer,
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
            span.set_attribute("kafka.access", "poll")

            try:
                res = wrapped(*args, **kwargs)
                if res:
                    span.set_attribute("kafka.service", res.topic())
            except Exception as exc:
                span.record_exception(exc)
            else:
                return res

    # Apply the monkey patch
    confluent_kafka.Producer = InstanaConfluentKafkaProducer
    confluent_kafka.Consumer = InstanaConfluentKafkaConsumer

    wrapt.wrap_function_wrapper(
        InstanaConfluentKafkaProducer, "produce", trace_kafka_produce
    )
    wrapt.wrap_function_wrapper(
        InstanaConfluentKafkaConsumer, "consume", trace_kafka_consume
    )
    wrapt.wrap_function_wrapper(InstanaConfluentKafkaConsumer, "poll", trace_kafka_poll)

    logger.debug("Instrumenting Kafka (confluent_kafka)")
except ImportError:
    pass
