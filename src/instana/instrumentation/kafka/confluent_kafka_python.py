# (c) Copyright IBM Corp. 2025


try:
    import contextvars
    from typing import Any, Callable, Dict, List, Optional, Tuple

    import confluent_kafka  # noqa: F401
    import wrapt
    from confluent_kafka import Consumer, Producer
    from opentelemetry import context, trace
    from opentelemetry.trace import SpanKind

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import get_tracer
    from instana.span.span import InstanaSpan
    from instana.util.traceutils import get_tracer_tuple, tracing_is_off

    consumer_token = None
    consumer_span = contextvars.ContextVar("confluent_kafka_consumer_span")

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

        def close(self) -> None:
            return super().close()

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

        # Get the topic from either args or kwargs
        topic = args[0] if args else kwargs.get("topic", "")

        is_suppressed = tracer.exporter._HostAgent__is_endpoint_ignored(
            "kafka",
            "produce",
            topic,
        )

        with tracer.start_as_current_span(
            "kafka-producer", span_context=parent_context, kind=SpanKind.PRODUCER
        ) as span:
            span.set_attribute("kafka.service", topic)
            span.set_attribute("kafka.access", "produce")

            # context propagation
            #
            # As stated in the official documentation at
            # https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html#pythonclient-producer,
            # headers can be either a list of (key, value) pairs or a
            # dictionary. To maintain compatibility with the headers for the
            # Kafka Python library, we will use a list of tuples.
            headers = args[6] if len(args) > 6 else kwargs.get("headers", [])

            # Initialize headers if it's None
            if headers is None:
                headers = []
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
        topic: Optional[str] = "",
        headers: Optional[List[Tuple[str, bytes]]] = [],
        exception: Optional[str] = None,
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
                for header_name, header_value in headers:
                    if header_name == "x_instana_l_s" and header_value == b"0":
                        is_suppressed = True
                        break

            if is_suppressed:
                return

            parent_context = (
                parent_span.get_span_context()
                if parent_span
                else (
                    tracer.extract(
                        Format.KAFKA_HEADERS,
                        headers,
                        disable_w3c_trace_context=True,
                    )
                    if tracer.exporter.options.kafka_trace_correlation
                    else None
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
        except Exception as e:
            logger.debug(
                f"Error while creating kafka-consumer span: {e}"
            )  # pragma: no cover

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

    def trace_kafka_consume(
        wrapped: Callable[..., InstanaConfluentKafkaConsumer.consume],
        instance: InstanaConfluentKafkaConsumer,
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> List[confluent_kafka.Message]:
        res = None
        exception = None

        try:
            res = wrapped(*args, **kwargs)
            for message in res:
                create_span("consume", message.topic(), message.headers())
            return res
        except Exception as exc:
            exception = exc
            create_span("consume", exception=exception)

    def trace_kafka_close(
        wrapped: Callable[..., InstanaConfluentKafkaConsumer.close],
        instance: InstanaConfluentKafkaConsumer,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> None:
        try:
            # Close any existing consumer span before closing the consumer
            span = consumer_span.get(None)
            if span is not None:
                close_consumer_span(span)

            # Execute the actual close operation
            res = wrapped(*args, **kwargs)

            logger.debug("Kafka consumer closed and spans cleaned up")
            return res

        except Exception:
            # Still try to clean up the span even if close fails
            span = consumer_span.get(None)
            if span is not None:
                close_consumer_span(span)

    def trace_kafka_poll(
        wrapped: Callable[..., InstanaConfluentKafkaConsumer.poll],
        instance: InstanaConfluentKafkaConsumer,
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> Optional[confluent_kafka.Message]:
        res = None
        exception = None

        try:
            res = wrapped(*args, **kwargs)
            create_span("poll", res.topic(), res.headers())
            return res
        except Exception as exc:
            exception = exc
            create_span(
                "poll",
                next(iter(instance.list_topics().topics)),
                exception=exception,
            )

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
    wrapt.wrap_function_wrapper(
        InstanaConfluentKafkaConsumer, "close", trace_kafka_close
    )

    logger.debug("Instrumenting Kafka (confluent_kafka)")
except ImportError:
    pass
