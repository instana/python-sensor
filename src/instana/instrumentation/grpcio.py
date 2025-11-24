# (c) Copyright IBM Corp. 2021, 2025
# (c) Copyright Instana Inc. 2019


try:
    from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple, Union

    import grpc
    from grpc._channel import (
        _StreamStreamMultiCallable,
        _StreamUnaryMultiCallable,
        _UnaryStreamMultiCallable,
        _UnaryUnaryMultiCallable,
    )

    if TYPE_CHECKING:
        from grpc._server import _Server

    import wrapt

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import get_tracer
    from instana.span.span import get_current_span

    SUPPORTED_TYPES = [
        _UnaryUnaryMultiCallable,
        _StreamUnaryMultiCallable,
        _UnaryStreamMultiCallable,
        _StreamStreamMultiCallable,
    ]

    def collect_attributes(span, instance, argv, kwargs):
        try:
            span.set_attribute("rpc.flavor", "grpc")

            if type(instance) in SUPPORTED_TYPES:
                method = instance._method.decode()
                target = instance._channel.target().decode()
            elif type(argv[0]) is grpc._cython.cygrpc.RequestCallEvent:
                method = argv[0].call_details.method.decode()
                target = argv[0].call_details.host.decode()
            elif len(argv) > 2:
                method = argv[2][2][1]._method.decode()
                target = argv[2][2][1]._channel.target().decode()

            span.set_attribute("rpc.call", method)

            if ":///" in target:
                _, target, *_ = target.split(":///")
            parts = target.split(":")
            if len(parts) == 2:
                span.set_attribute("rpc.host", parts[0])
                span.set_attribute("rpc.port", parts[1])
        except Exception:
            logger.debug("grpc.collect_attributes non-fatal error", exc_info=True)
        return span

    def create_span(
        wrapped: Callable[..., object],
        instance: Union[
            _UnaryUnaryMultiCallable,
            _StreamUnaryMultiCallable,
            _UnaryStreamMultiCallable,
            _StreamStreamMultiCallable,
        ],
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
        call_type: str,
        record_exception: bool = True,
    ) -> object:
        parent_span = get_current_span()
        tracer = get_tracer()

        # If we're not tracing, just return
        if not parent_span.is_recording():
            return wrapped(*argv, **kwargs)

        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span(
            "rpc-client", span_context=parent_context, record_exception=record_exception
        ) as span:
            try:
                if "metadata" not in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(
                    span.context,
                    Format.BINARY,
                    kwargs["metadata"],
                    disable_w3c_trace_context=True,
                )
                collect_attributes(span, instance, argv, kwargs)
                span.set_attribute("rpc.call_type", call_type)

                rv = wrapped(*argv, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return rv

    @wrapt.patch_function_wrapper("grpc._channel", "_UnaryUnaryMultiCallable.with_call")
    def unary_unary_with_call_with_instana(
        wrapped: Callable[..., object],
        instance: _UnaryUnaryMultiCallable,
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        return create_span(wrapped, instance, argv, kwargs, call_type="unary")

    @wrapt.patch_function_wrapper("grpc._channel", "_UnaryUnaryMultiCallable.future")
    def unary_unary_future_with_instana(
        wrapped: Callable[..., object],
        instance: _UnaryUnaryMultiCallable,
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        return create_span(wrapped, instance, argv, kwargs, call_type="unary")

    @wrapt.patch_function_wrapper("grpc._channel", "_UnaryUnaryMultiCallable.__call__")
    def unary_unary_call_with_instana(
        wrapped: Callable[..., object],
        instance: _UnaryUnaryMultiCallable,
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        return create_span(
            wrapped, instance, argv, kwargs, call_type="unary", record_exception=False
        )

    @wrapt.patch_function_wrapper("grpc._channel", "_StreamUnaryMultiCallable.__call__")
    def stream_unary_call_with_instana(
        wrapped: Callable[..., object],
        instance: _StreamUnaryMultiCallable,
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        return create_span(wrapped, instance, argv, kwargs, call_type="stream")

    @wrapt.patch_function_wrapper(
        "grpc._channel", "_StreamUnaryMultiCallable.with_call"
    )
    def stream_unary_with_call_with_instana(
        wrapped: Callable[..., object],
        instance: _StreamUnaryMultiCallable,
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        return create_span(wrapped, instance, argv, kwargs, call_type="stream")

    @wrapt.patch_function_wrapper("grpc._channel", "_StreamUnaryMultiCallable.future")
    def stream_unary_future_with_instana(
        wrapped: Callable[..., object],
        instance: _StreamUnaryMultiCallable,
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        return create_span(wrapped, instance, argv, kwargs, call_type="stream")

    @wrapt.patch_function_wrapper("grpc._channel", "_UnaryStreamMultiCallable.__call__")
    def unary_stream_call_with_instana(
        wrapped: Callable[..., object],
        instance: _UnaryStreamMultiCallable,
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        return create_span(wrapped, instance, argv, kwargs, call_type="stream")

    @wrapt.patch_function_wrapper(
        "grpc._channel", "_StreamStreamMultiCallable.__call__"
    )
    def stream_stream_call_with_instana(
        wrapped: Callable[..., object],
        instance: _StreamStreamMultiCallable,
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        return create_span(wrapped, instance, argv, kwargs, call_type="stream")

    @wrapt.patch_function_wrapper("grpc._server", "_call_behavior")
    def call_behavior_with_instana(
        wrapped: Callable[..., object],
        instance: "_Server",
        argv: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        tracer = get_tracer()
        # Prep any incoming context headers
        metadata = argv[0].invocation_metadata
        metadata_dict = {}
        for c in metadata:
            metadata_dict[c.key] = c.value

        ctx = tracer.extract(
            Format.BINARY, metadata_dict, disable_w3c_trace_context=True
        )

        with tracer.start_as_current_span("rpc-server", span_context=ctx) as span:
            try:
                collect_attributes(span, instance, argv, kwargs)
                rv = wrapped(*argv, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return rv

    logger.debug("Instrumenting grpcio")
except ImportError:
    pass
