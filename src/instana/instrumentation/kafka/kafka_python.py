# (c) Copyright IBM Corp. 2025

try:
    import inspect
    from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

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
        is_suppressed = tracer.exporter._HostAgent__is_endpoint_ignored(
            "kafka",
            "send",
            args[0],
        )
        with tracer.start_as_current_span(
            "kafka-producer", span_context=parent_context, kind=SpanKind.PRODUCER
        ) as span:
            span.set_attribute("kafka.service", args[0])
            span.set_attribute("kafka.access", "send")

            # context propagation
            headers = kwargs.get("headers", [])
            suppression_header = {"x_instana_l_s": "0" if is_suppressed else "1"}
            headers.append(suppression_header)

            tracer.inject(
                span.context,
                Format.KAFKA_HEADERS,
                headers,
                disable_w3c_trace_context=True,
            )

            headers.remove(suppression_header)

            if tracer.exporter.options.kafka_trace_correlation:
                kwargs["headers"] = headers
            try:
                res = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return res

    def create_span(
        span_type: str,
        topic: Optional[str],
        headers: Optional[List[Tuple[str, bytes]]] = [],
        exception: Optional[str] = None,
    ) -> None:
        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = (
            parent_span.get_span_context()
            if parent_span
            else tracer.extract(
                Format.KAFKA_HEADERS,
                headers,
                disable_w3c_trace_context=True,
            )
        )
        with tracer.start_as_current_span(
            "kafka-consumer", span_context=parent_context, kind=SpanKind.CONSUMER
        ) as span:
            if topic:
                span.set_attribute("kafka.service", topic)
            span.set_attribute("kafka.access", span_type)
            if exception:
                span.record_exception(exception)

    @wrapt.patch_function_wrapper("kafka", "KafkaConsumer.__next__")
    def trace_kafka_consume(
        wrapped: Callable[..., "kafka.KafkaConsumer.__next__"],
        instance: "kafka.KafkaConsumer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> "FutureRecordMetadata":
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        exception = None
        res = None

        try:
            res = wrapped(*args, **kwargs)
        except Exception as exc:
            exception = exc
        finally:
            if res:
                create_span(
                    "consume",
                    res.topic if res else list(instance.subscription())[0],
                    res.headers,
                )
            else:
                create_span(
                    "consume", list(instance.subscription())[0], exception=exception
                )

        return res

    @wrapt.patch_function_wrapper("kafka", "KafkaConsumer.poll")
    def trace_kafka_poll(
        wrapped: Callable[..., "kafka.KafkaConsumer.poll"],
        instance: "kafka.KafkaConsumer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        # The KafkaConsumer.consume() from the kafka-python-ng call the
        # KafkaConsumer.poll() internally, so we do not consider it here.
        if any(
            frame.function == "trace_kafka_consume"
            for frame in inspect.getouterframes(inspect.currentframe(), 2)
        ):
            return wrapped(*args, **kwargs)

        exception = None
        res = None

        try:
            res = wrapped(*args, **kwargs)
        except Exception as exc:
            exception = exc
        finally:
            if res:
                for partition, consumer_records in res.items():
                    for message in consumer_records:
                        create_span(
                            "poll",
                            partition.topic,
                            message.headers if hasattr(message, "headers") else [],
                        )
            else:
                create_span(
                    "poll", list(instance.subscription())[0], exception=exception
                )

        return res

    logger.debug("Instrumenting Kafka (kafka-python)")
except ImportError:
    pass
