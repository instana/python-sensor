# (c) Copyright IBM Corp. 2025


try:
    import contextvars
    import inspect
    from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

    import kafka  # noqa: F401
    import wrapt
    from opentelemetry import context, trace
    from opentelemetry.trace import SpanKind

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import get_tracer
    from instana.span.span import InstanaSpan
    from instana.util.traceutils import get_tracer_tuple, tracing_is_off

    if TYPE_CHECKING:
        from kafka.producer.future import FutureRecordMetadata

    consumer_token = None
    consumer_span = contextvars.ContextVar("kafka_python_consumer_span")

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

        # Get the topic from either args or kwargs
        topic = args[0] if args else kwargs.get("topic", "")

        is_suppressed = tracer.exporter._HostAgent__is_endpoint_ignored(
            "kafka",
            "send",
            topic,
        )
        with tracer.start_as_current_span(
            "kafka-producer", span_context=parent_context, kind=SpanKind.PRODUCER
        ) as span:
            span.set_attribute("kafka.service", topic)
            span.set_attribute("kafka.access", "send")

            # context propagation
            headers = kwargs.get("headers", [])
            if not is_suppressed and ("x_instana_l_s", b"0") in headers:
                is_suppressed = True

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
                return res
            except Exception as exc:
                span.record_exception(exc)

    def create_span(
        span_type: str,
        topic: Optional[str],
        headers: Optional[List[Tuple[str, bytes]]] = [],
        exception: Optional[Exception] = None,
    ) -> None:
        try:
            span = consumer_span.get(None)
            if span is not None:
                close_consumer_span(span)

            tracer, parent_span, _ = get_tracer_tuple()

            if not tracer:
                tracer = get_tracer()

            is_suppressed = False
            if topic:
                is_suppressed = tracer.exporter._HostAgent__is_endpoint_ignored(
                    "kafka",
                    span_type,
                    topic,
                )

            if not is_suppressed and headers:
                if ("x_instana_l_s", b"0") in headers:
                    is_suppressed = True

            if is_suppressed:
                return

            parent_context = (
                parent_span.get_span_context()
                if parent_span
                else tracer.extract(
                    Format.KAFKA_HEADERS,
                    headers,
                    disable_w3c_trace_context=True,
                )
            )
            span = tracer.start_span(
                "kafka-consumer", span_context=parent_context, kind=SpanKind.CONSUMER
            )
            if topic:
                span.set_attribute("kafka.service", topic)
            span.set_attribute("kafka.access", span_type)
            if exception:
                span.record_exception(exception)
                span.end()

            save_consumer_span_into_context(span)
        except Exception:
            pass

    def save_consumer_span_into_context(span: "InstanaSpan") -> None:
        global consumer_token
        ctx = trace.set_span_in_context(span)
        consumer_token = context.attach(ctx)
        consumer_span.set(span)

    def close_consumer_span(span: "InstanaSpan") -> None:
        global consumer_token
        if span.is_recording():
            span.end()
            consumer_span.set(None)
        if consumer_token is not None:
            context.detach(consumer_token)
            consumer_token = None

    def clear_context() -> None:
        global consumer_token
        context.attach(trace.set_span_in_context(None))
        consumer_token = None
        consumer_span.set(None)

    @wrapt.patch_function_wrapper("kafka", "KafkaConsumer.__next__")
    def trace_kafka_consume(
        wrapped: Callable[..., "kafka.KafkaConsumer.__next__"],
        instance: "kafka.KafkaConsumer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> "FutureRecordMetadata":
        exception = None
        res = None

        try:
            res = wrapped(*args, **kwargs)
            create_span(
                "consume",
                res.topic if res else list(instance.subscription())[0],
                res.headers,
            )
            return res
        except StopIteration:
            pass
        except Exception as exc:
            exception = exc
            create_span(
                "consume", list(instance.subscription())[0], exception=exception
            )

    @wrapt.patch_function_wrapper("kafka", "KafkaConsumer.close")
    def trace_kafka_close(
        wrapped: Callable[..., None],
        instance: "kafka.KafkaConsumer",
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> None:
        try:
            span = consumer_span.get(None)
            if span is not None:
                close_consumer_span(span)
        except Exception as e:
            logger.debug(
                f"Error while closing kafka-consumer span: {e}"
            )  # pragma: no cover
        return wrapped(*args, **kwargs)

    @wrapt.patch_function_wrapper("kafka", "KafkaConsumer.poll")
    def trace_kafka_poll(
        wrapped: Callable[..., "kafka.KafkaConsumer.poll"],
        instance: "kafka.KafkaConsumer",
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
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
            for partition, consumer_records in res.items():
                for message in consumer_records:
                    create_span(
                        "poll",
                        partition.topic,
                        message.headers if hasattr(message, "headers") else [],
                    )
            return res
        except Exception as exc:
            exception = exc
            create_span("poll", list(instance.subscription())[0], exception=exception)

    logger.debug("Instrumenting Kafka (kafka-python)")
except ImportError:
    pass
