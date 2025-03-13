# coding: utf-8
# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

try:
    import types
    from typing import (
        TYPE_CHECKING,
        Any,
        Callable,
        Dict,
        Iterator,
        Optional,
        Tuple,
        Union,
    )

    import pika
    import wrapt

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import tracer
    from instana.util.traceutils import get_tracer_tuple, tracing_is_off

    if TYPE_CHECKING:
        import pika.adapters.blocking_connection
        import pika.channel
        import pika.connection

        from instana.span.span import InstanaSpan

    def _extract_broker_attributes(
        span: "InstanaSpan", conn: pika.connection.Connection
    ) -> None:
        span.set_attribute("address", f"{conn.params.host}:{conn.params.port}")

    def _extract_publisher_attributes(
        span: "InstanaSpan",
        conn: pika.connection.Connection,
        exchange: str,
        routing_key: str,
    ) -> None:
        _extract_broker_attributes(span, conn)

        span.set_attribute("sort", "publish")
        span.set_attribute("key", routing_key)
        span.set_attribute("exchange", exchange)

    def _extract_consumer_tags(
        span: "InstanaSpan", conn: pika.connection.Connection, queue: str
    ) -> None:
        _extract_broker_attributes(span, conn)

        span.set_attribute("sort", "consume")
        span.set_attribute("queue", queue)

    @wrapt.patch_function_wrapper("pika.channel", "Channel.basic_publish")
    def basic_publish_with_instana(
        wrapped: Callable[..., pika.channel.Channel.basic_publish],
        instance: pika.channel.Channel,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        def _bind_args(
            exchange: str,
            routing_key: str,
            body: str,
            properties: Optional[object] = None,
            *args: object,
            **kwargs: object,
        ) -> Tuple[object, ...]:
            return (exchange, routing_key, body, properties, args, kwargs)

        # If we're not tracing, just return
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        (exchange, routing_key, body, properties, args, kwargs) = _bind_args(
            *args, **kwargs
        )

        with tracer.start_as_current_span(
            "rabbitmq", span_context=parent_context
        ) as span:
            try:
                _extract_publisher_attributes(
                    span,
                    conn=instance.connection,
                    routing_key=routing_key,
                    exchange=exchange,
                )
            except Exception:
                logger.debug("pika publish_with_instana error: ", exc_info=True)

            # context propagation
            properties = properties or pika.BasicProperties()
            properties.headers = properties.headers or {}

            tracer.inject(
                span.context,
                Format.HTTP_HEADERS,
                properties.headers,
                disable_w3c_trace_context=True,
            )
            args = (exchange, routing_key, body, properties) + args

            try:
                rv = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return rv

    def basic_get_with_instana(
        wrapped: Callable[
            ...,
            Union[pika.channel.Channel.basic_get, pika.channel.Channel.basic_consume],
        ],
        instance: pika.channel.Channel,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        def _bind_args(*args: object, **kwargs: object) -> Tuple[object, ...]:
            args = list(args)
            queue = kwargs.pop("queue", None) or args.pop(0)
            callback = (
                kwargs.pop("callback", None)
                or kwargs.pop("on_message_callback", None)
                or args.pop(0)
            )
            return (queue, callback, tuple(args), kwargs)

        queue, callback, args, kwargs = _bind_args(*args, **kwargs)

        def _cb_wrapper(
            channel: pika.channel.Channel,
            method: pika.spec.Basic,
            properties: pika.BasicProperties,
            body: str,
        ) -> None:
            parent_context = tracer.extract(
                Format.HTTP_HEADERS, properties.headers, disable_w3c_trace_context=True
            )

            with tracer.start_as_current_span(
                "rabbitmq", span_context=parent_context
            ) as span:
                try:
                    _extract_consumer_tags(span, conn=instance.connection, queue=queue)
                except Exception:
                    logger.debug("pika basic_get_with_instana error: ", exc_info=True)

                try:
                    callback(channel, method, properties, body)
                except Exception as exc:
                    span.record_exception(exc)

        args = (queue, _cb_wrapper) + args
        return wrapped(*args, **kwargs)

    @wrapt.patch_function_wrapper(
        "pika.adapters.blocking_connection", "BlockingChannel.basic_consume"
    )
    def basic_consume_with_instana(
        wrapped: Callable[
            ..., pika.adapters.blocking_connection.BlockingChannel.basic_consume
        ],
        instance: pika.adapters.blocking_connection.BlockingChannel,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        def _bind_args(
            queue: str,
            on_message_callback: object,
            *args: object,
            **kwargs: object,
        ) -> Tuple[object, ...]:
            return (queue, on_message_callback, args, kwargs)

        queue, on_message_callback, args, kwargs = _bind_args(*args, **kwargs)

        def _cb_wrapper(
            channel: pika.channel.Channel,
            method: pika.spec.Basic,
            properties: pika.BasicProperties,
            body: str,
        ) -> None:
            parent_context = tracer.extract(
                Format.HTTP_HEADERS, properties.headers, disable_w3c_trace_context=True
            )

            with tracer.start_as_current_span(
                "rabbitmq", span_context=parent_context
            ) as span:
                try:
                    _extract_consumer_tags(
                        span, conn=instance.connection._impl, queue=queue
                    )
                except Exception:
                    logger.debug(
                        "pika basic_consume_with_instana error:", exc_info=True
                    )

                try:
                    on_message_callback(channel, method, properties, body)
                except Exception as exc:
                    span.record_exception(exc)

        args = (queue, _cb_wrapper) + args
        return wrapped(*args, **kwargs)

    @wrapt.patch_function_wrapper(
        "pika.adapters.blocking_connection", "BlockingChannel.consume"
    )
    def consume_with_instana(
        wrapped: Callable[..., pika.adapters.blocking_connection.BlockingChannel],
        instance: pika.adapters.blocking_connection.BlockingChannel,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        def _bind_args(
            queue: str, *args: object, **kwargs: object
        ) -> Tuple[object, ...]:
            return (queue, args, kwargs)

        (queue, args, kwargs) = _bind_args(*args, **kwargs)

        def _consume(gen: Iterator[object]) -> object:
            for yielded in gen:
                # Bypass the delivery created due to inactivity timeout
                if not yielded or not any(yielded):
                    yield yielded
                    continue

                (method_frame, properties, body) = yielded

                parent_context = tracer.extract(
                    Format.HTTP_HEADERS,
                    properties.headers,
                    disable_w3c_trace_context=True,
                )
                with tracer.start_as_current_span(
                    "rabbitmq", span_context=parent_context
                ) as span:
                    try:
                        _extract_consumer_tags(
                            span, conn=instance.connection._impl, queue=queue
                        )
                    except Exception:
                        logger.debug("consume_with_instana: ", exc_info=True)

                    try:
                        yield yielded
                    except GeneratorExit:
                        gen.close()
                    except Exception as exc:
                        span.record_exception(exc)

        args = (queue,) + args
        res = wrapped(*args, **kwargs)

        if isinstance(res, types.GeneratorType):
            return _consume(res)
        else:
            return res

    @wrapt.patch_function_wrapper(
        "pika.adapters.blocking_connection", "BlockingChannel.__init__"
    )
    def _BlockingChannel___init__(
        wrapped: Callable[
            ..., pika.adapters.blocking_connection.BlockingChannel.__init__
        ],
        instance: pika.adapters.blocking_connection.BlockingChannel,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        ret = wrapped(*args, **kwargs)
        impl = getattr(instance, "_impl", None)

        if impl and hasattr(impl.basic_consume, "__wrapped__"):
            impl.basic_consume = impl.basic_consume.__wrapped__

        return ret

    wrapt.wrap_function_wrapper(
        "pika.channel", "Channel.basic_get", basic_get_with_instana
    )
    wrapt.wrap_function_wrapper(
        "pika.channel", "Channel.basic_consume", basic_get_with_instana
    )

    logger.debug("Instrumenting pika")
except ImportError:
    pass
