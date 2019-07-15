from __future__ import absolute_import

import wrapt
import opentracing

from ..log import logger
from ..singletons import tracer

try:
    import grpc


    @wrapt.patch_function_wrapper('grpc._channel', '_UnaryUnaryMultiCallable.with_call')
    def with_call_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None or parent_span.operation_name == "rpc-client":
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if "metadata" not in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv


    @wrapt.patch_function_wrapper('grpc._channel', '_UnaryUnaryMultiCallable.__call__')
    def call_with_instana(wrapped, instance, argv, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None or parent_span.operation_name == "rpc-client":
            return wrapped(*argv, **kwargs)

        with tracer.start_active_span("rpc-client", child_of=parent_span) as scope:
            try:
                if not "metadata" in kwargs:
                    kwargs["metadata"] = []

                kwargs["metadata"] = tracer.inject(scope.span.context, opentracing.Format.BINARY, kwargs['metadata'])

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
                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

except ImportError:
    pass
