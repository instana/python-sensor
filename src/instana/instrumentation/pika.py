# coding: utf-8
# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


try:
    import importlib.util
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
    from opentelemetry.context import get_current

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import get_tracer
    from instana.util.traceutils import get_tracer_tuple

    if TYPE_CHECKING:
        import pika.adapters.blocking_connection
        import pika.adapters.thread_safe_connection
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

    def _get_pika_channel(
        instance: Union[
            "pika.channel.Channel", "pika.adapters.thread_safe_connection.Channel"
        ],
    ) -> "pika.channel.Channel":
        """Return the pika channel behind the given channel.

        The thread-safe channel (pika >= 1.5.0) keeps the pika channel in
        `_channel`; every other caller already is a pika channel.

        :param instance: A pika channel or a thread-safe channel.
        :return: The pika channel.
        """
        return getattr(instance, "_channel", instance)

    def _get_consumer_connection(
        instance: Union[
            "pika.adapters.blocking_connection.BlockingChannel",
            "pika.adapters.thread_safe_connection.Channel",
        ],
    ) -> "pika.connection.Connection":
        """Return the pika connection a consumer channel is bound to.

        The thread-safe channel (pika >= 1.5.0) exposes the pika channel in
        `_channel`, the BlockingChannel the connection implementation.

        :param instance: A BlockingChannel or a thread-safe channel.
        :return: The pika connection.
        """
        if hasattr(instance, "_channel"):
            return instance._channel.connection
        return instance.connection._impl

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

        tracer, _, _ = get_tracer_tuple()

        # If we're not tracing, just return
        if not tracer:
            return wrapped(*args, **kwargs)

        parent_context = get_current()

        (exchange, routing_key, body, properties, args, kwargs) = _bind_args(
            *args, **kwargs
        )

        with tracer.start_as_current_span("rabbitmq", context=parent_context) as span:
            try:
                _extract_publisher_attributes(
                    span,
                    conn=_get_pika_channel(instance).connection,
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
        tracer = get_tracer()

        if not tracer:
            return wrapped(*args, **kwargs)

        def _bind_args(*args: object, **kwargs: object) -> tuple[object, ...]:
            args = list(args)
            queue = kwargs.pop("queue") if "queue" in kwargs else args.pop(0)
            # `basic_consume` also takes a `callback` (Basic.ConsumeOk) next to
            # `on_message_callback`, it must be passed through untouched.
            if "on_message_callback" in kwargs:
                callback = kwargs.pop("on_message_callback")
            elif args:
                callback = args.pop(0)
            else:
                callback = kwargs.pop("callback")
            return (queue, callback, tuple(args), kwargs)

        queue, callback, args, kwargs = _bind_args(*args, **kwargs)

        def _cb_wrapper(
            channel: pika.channel.Channel,
            method: pika.spec.Basic,
            properties: pika.BasicProperties,
            body: str,
        ) -> None:
            tracer = get_tracer()
            parent_context = tracer.extract(
                Format.HTTP_HEADERS, properties.headers, disable_w3c_trace_context=True
            )

            with tracer.start_as_current_span(
                "rabbitmq", context=parent_context
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
        tracer = get_tracer()

        if not tracer:
            return wrapped(*args, **kwargs)

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
            tracer = get_tracer()
            parent_context = tracer.extract(
                Format.HTTP_HEADERS, properties.headers, disable_w3c_trace_context=True
            )

            with tracer.start_as_current_span(
                "rabbitmq", context=parent_context
            ) as span:
                try:
                    _extract_consumer_tags(
                        span, conn=_get_consumer_connection(instance), queue=queue
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
        tracer = get_tracer()

        if not tracer:
            return wrapped(*args, **kwargs)

        def _bind_args(
            queue: str, *args: object, **kwargs: object
        ) -> Tuple[object, ...]:
            return (queue, args, kwargs)

        (queue, args, kwargs) = _bind_args(*args, **kwargs)

        def _consume(gen: Iterator[object]) -> object:
            tracer = get_tracer()
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
                    "rabbitmq", context=parent_context
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

    def _ThreadSafeChannel___init__(
        wrapped: Callable[..., "pika.adapters.thread_safe_connection.Channel.__init__"],
        instance: "pika.adapters.thread_safe_connection.Channel",
        args: tuple[object, ...],
        kwargs: dict[str, Any],
    ) -> object:
        """Trace the consumer callback at the thread-safe channel level.

        The callback is dispatched to a worker thread, so the wrapper of the
        underlying pika channel is removed to avoid tracing it twice.

        :param wrapped: The original `Channel.__init__`.
        :param instance: The thread-safe channel being initialized.
        :param args: Positional arguments of `Channel.__init__`.
        :param kwargs: Keyword arguments of `Channel.__init__`.
        :return: The value returned by `Channel.__init__`.
        """
        ret = wrapped(*args, **kwargs)

        if (impl := getattr(instance, "_channel", None)) and hasattr(
            impl.basic_consume, "__wrapped__"
        ):
            impl.basic_consume = impl.basic_consume.__wrapped__

        return ret

    wrapt.wrap_function_wrapper(
        "pika.channel", "Channel.basic_get", basic_get_with_instana
    )
    wrapt.wrap_function_wrapper(
        "pika.channel", "Channel.basic_consume", basic_get_with_instana
    )

    # The thread-safe connection is only available since pika 1.5.0
    if importlib.util.find_spec("pika.adapters.thread_safe_connection"):
        wrapt.wrap_function_wrapper(
            "pika.adapters.thread_safe_connection",
            "Channel.basic_publish",
            basic_publish_with_instana,
        )
        wrapt.wrap_function_wrapper(
            "pika.adapters.thread_safe_connection",
            "Channel.basic_consume",
            basic_consume_with_instana,
        )
        wrapt.wrap_function_wrapper(
            "pika.adapters.thread_safe_connection",
            "Channel.__init__",
            _ThreadSafeChannel___init__,
        )

    logger.debug("Instrumenting pika")
except ImportError:
    pass
