# (c) Copyright IBM Corp. 2025

try:
    import aioamqp
    from typing import Any, Callable, Dict, Tuple

    import wrapt
    from opentelemetry.trace.status import StatusCode

    from instana.log import logger
    from instana.util.traceutils import get_tracer_tuple, tracing_is_off

    @wrapt.patch_function_wrapper("aioamqp.channel", "Channel.basic_publish")
    async def basic_publish_with_instana(
        wrapped: Callable[..., aioamqp.connect],
        instance: object,
        argv: Tuple[object, Tuple[object, ...]],
        kwargs: Dict[str, Any],
    ) -> object:
        if tracing_is_off():
            return await wrapped(*argv, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None
        with tracer.start_as_current_span(
            "aioamqp-publisher", span_context=parent_context
        ) as span:
            try:
                span.set_attribute("amqp.command", "publish")
                span.set_attribute("amqp.routing_key", kwargs.get("routing_key"))

                protocol = getattr(instance, "protocol", None)
                transport = getattr(protocol, "_transport", None)
                extra = getattr(transport, "_extra", {}) if transport else {}
                peername = extra.get("peername")
                if (
                    peername
                    and isinstance(peername, (list, tuple))
                    and len(peername) >= 2
                ):
                    connection_info = f"{peername[0]}:{peername[1]}"
                else:
                    connection_info = "unknown"
                span.set_attribute("amqp.connection", connection_info)

                response = await wrapped(*argv, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
                logger.debug(f"aioamqp basic_publish_with_instana error: {exc}")
            else:
                return response

    @wrapt.patch_function_wrapper("aioamqp.channel", "Channel.basic_consume")
    async def basic_consume_with_instana(
        wrapped: Callable[..., aioamqp.connect],
        instance: object,
        argv: Tuple[object, Tuple[object, ...]],
        kwargs: Dict[str, Any],
    ) -> object:
        if tracing_is_off():
            return await wrapped(*argv, **kwargs)

        callback = argv[0]
        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        @wrapt.decorator
        async def callback_wrapper(
            wrapped_callback: Callable[..., aioamqp.connect],
            instance: Any,
            args: Tuple,
            kwargs: Dict,
        ) -> object:
            with tracer.start_as_current_span(
                "aioamqp-consumer", span_context=parent_context
            ) as span:
                try:
                    span.set_status(StatusCode.OK)
                    span.set_attribute("amqp.command", "consume")
                    span.set_attribute("amqp.routing_key", args[2].routing_key)

                    protocol = getattr(args[0], "protocol", None)
                    transport = getattr(protocol, "_transport", None)
                    extra = getattr(transport, "_extra", {}) if transport else {}
                    peername = extra.get("peername")
                    if (
                        peername
                        and isinstance(peername, (list, tuple))
                        and len(peername) >= 2
                    ):
                        connection_info = f"{peername[0]}:{peername[1]}"
                    else:
                        connection_info = "unknown"
                    span.set_attribute("amqp.connection", connection_info)

                    response = await wrapped_callback(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    logger.debug(f"aioamqp basic_consume_with_instana error: {exc}")
                else:
                    return response

        wrapped_callback = callback_wrapper(callback)
        argv = (wrapped_callback,) + argv[1:]

        return await wrapped(*argv, **kwargs)

    logger.debug("Instrumenting aioamqp")

except ImportError:
    pass
