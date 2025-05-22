# (c) Copyright IBM Corp. 2025

try:
    import aio_pika
    import wrapt
    from typing import (
        TYPE_CHECKING,
        Dict,
        Any,
        Callable,
        Tuple,
        Type,
        Optional,
    )

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.util.traceutils import get_tracer_tuple, tracing_is_off
    from instana.singletons import tracer

    if TYPE_CHECKING:
        from instana.span.span import InstanaSpan
        from aio_pika.exchange import Exchange
        from aiormq.abc import ConfirmationFrameType
        from aio_pika.abc import ConsumerTag, AbstractMessage
        from aio_pika.queue import Queue, QueueIterator

    def _extract_span_attributes(
        span: "InstanaSpan", connection, sort: str, routing_key: str, exchange: str
    ) -> None:
        span.set_attribute("address", str(connection.url))

        span.set_attribute("sort", sort)
        span.set_attribute("key", routing_key)
        span.set_attribute("exchange", exchange)

    @wrapt.patch_function_wrapper("aio_pika", "Exchange.publish")
    async def publish_with_instana(
        wrapped: Callable[..., Optional["ConfirmationFrameType"]],
        instance: "Exchange",
        args: Tuple[object],
        kwargs: Dict[str, Any],
    ) -> Optional["ConfirmationFrameType"]:
        if tracing_is_off():
            return await wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span(
            "rabbitmq", span_context=parent_context
        ) as span:
            connection = instance.channel._connection
            _extract_span_attributes(
                span, connection, "publish", kwargs["routing_key"], instance.name
            )

            message = args[0]
            tracer.inject(
                span.context,
                Format.HTTP_HEADERS,
                message.properties.headers,
                disable_w3c_trace_context=True,
            )
            try:
                response = await wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return response

    @wrapt.patch_function_wrapper("aio_pika", "Queue.consume")
    async def consume_with_instana(
        wrapped: Callable[..., "ConsumerTag"],
        instance: Type["Queue"],
        args: Tuple[object],
        kwargs: Dict[str, Any],
    ) -> "ConsumerTag":
        connection = instance.channel._connection
        callback = kwargs["callback"] if kwargs.get("callback") else args[0]

        @wrapt.decorator
        async def callback_wrapper(
            wrapped: Callable[[Type["AbstractMessage"]], Any],
            instance: Type["QueueIterator"],
            args: Tuple[Type["AbstractMessage"], ...],
            kwargs: Dict[str, Any],
        ) -> Callable[[Type["AbstractMessage"]], Any]:
            message = args[0]
            parent_context = tracer.extract(
                Format.HTTP_HEADERS, message.headers, disable_w3c_trace_context=True
            )
            with tracer.start_as_current_span(
                "rabbitmq", span_context=parent_context
            ) as span:
                _extract_span_attributes(
                    span, connection, "consume", message.routing_key, message.exchange
                )
            try:
                response = await wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return response

        wrapped_callback = callback_wrapper(callback)
        if kwargs.get("callback"):
            kwargs["callback"] = wrapped_callback
        else:
            args = (wrapped_callback,) + args[1:]

        return await wrapped(*args, **kwargs)

    logger.debug("Instrumenting aio-pika")

except ImportError:
    pass
