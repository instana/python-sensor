# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

from __future__ import absolute_import

import wrapt
import opentracing

from ..log import logger
from ..singletons import tracer

try:
    import grpc
    from grpc._channel import _UnaryUnaryMultiCallable, _StreamUnaryMultiCallable, \
                                _UnaryStreamMultiCallable, _StreamStreamMultiCallable

    SUPPORTED_TYPES = [ _UnaryUnaryMultiCallable,
                        _StreamUnaryMultiCallable,
                        _UnaryStreamMultiCallable,
                        _StreamStreamMultiCallable ]

    def collect_tags(span, instance, argv, kwargs):
        try:
            span.set_tag('rpc.flavor', 'grpc')

            if type(instance) in SUPPORTED_TYPES:
                method = instance._method.decode()
                target = instance._channel.target().decode()
            elif type(argv[0]) is grpc._cython.cygrpc.RequestCallEvent:
                method = argv[0].call_details.method.decode()
                target = argv[0].call_details.host.decode()
            elif len(argv) > 2:
                method = argv[2][2][1]._method.decode()
                target = argv[2][2][1]._channel.target().decode()

            span.set_tag('rpc.call', method)

            parts = target.split(':')
            if len(parts) == 2:
                span.set_tag('rpc.host', parts[0])
                span.set_tag('rpc.port', parts[1])
        except:
            logger.debug("grpc.collect_tags non-fatal error", exc_info=True)
        finally:
            return span


    @wrapt.patch_function_wrapper('grpc._channel', '_UnaryUnaryMultiCallable.with_call')
    def unary_unary_with_call_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if "metadata" not in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])
                collect_tags(scope.span, instance, argv, kwargs)
                scope.span.set_tag('rpc.call_type', 'unary')

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('grpc._channel', '_UnaryUnaryMultiCallable.future')
    def unary_unary_future_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if "metadata" not in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])
                collect_tags(scope.span, instance, argv, kwargs)
                scope.span.set_tag('rpc.call_type', 'unary')

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('grpc._channel', '_UnaryUnaryMultiCallable.__call__')
    def unary_unary_call_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if not "metadata" in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])
                collect_tags(scope.span, instance, argv, kwargs)
                scope.span.set_tag('rpc.call_type', 'unary')

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('grpc._channel', '_StreamUnaryMultiCallable.__call__')
    def stream_unary_call_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if not "metadata" in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])
                collect_tags(scope.span, instance, argv, kwargs)
                scope.span.set_tag('rpc.call_type', 'stream')

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('grpc._channel', '_StreamUnaryMultiCallable.with_call')
    def stream_unary_with_call_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if not "metadata" in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])
                collect_tags(scope.span, instance, argv, kwargs)
                scope.span.set_tag('rpc.call_type', 'stream')

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('grpc._channel', '_StreamUnaryMultiCallable.future')
    def stream_unary_future_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if not "metadata" in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])
                collect_tags(scope.span, instance, argv, kwargs)
                scope.span.set_tag('rpc.call_type', 'stream')

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('grpc._channel', '_UnaryStreamMultiCallable.__call__')
    def unary_stream_call_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if not "metadata" in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])
                collect_tags(scope.span, instance, argv, kwargs)
                scope.span.set_tag('rpc.call_type', 'stream')

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('grpc._channel', '_StreamStreamMultiCallable.__call__')
    def stream_stream_call_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if not "metadata" in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])
                collect_tags(scope.span, instance, argv, kwargs)
                scope.span.set_tag('rpc.call_type', 'stream')

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('grpc._server', '_call_behavior')
    def call_behavior_with_instana(wrapped, instance, argv, kwargs):
        # Prep any incoming context headers
        metadata = argv[0].invocation_metadata
        metadata_dict = {}
        for c in metadata:
            metadata_dict[c.key] = c.value

        ctx = tracer.extract(opentracing.Format.BINARY, metadata_dict)

        with tracer.start_active_span("rpc-server", child_of=ctx) as scope:
            try:
                collect_tags(scope.span, instance, argv, kwargs)
                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    logger.debug("Instrumenting grpcio")
except ImportError:
    pass
