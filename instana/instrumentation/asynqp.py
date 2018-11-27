from __future__ import absolute_import

import sys

import opentracing
import wrapt

from ..log import logger
from ..singletons import async_tracer

try:
    import asynqp

    @wrapt.patch_function_wrapper('asynqp.exchange','Exchange.publish')
    def publish_with_instana(wrapped, instance, argv, kwargs):
        parent_span = async_tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with async_tracer.start_active_span("rabbitmq", child_of=parent_span) as scope:
            host, port = instance.sender.protocol.transport._sock.getsockname()

            msg = argv[0]
            if msg.headers is None:
                msg.headers = {}
            async_tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, msg.headers)

            try:
                scope.span.set_tag("exchange", instance.name)
                scope.span.set_tag("sort", "publish")
                scope.span.set_tag("address", host + ":" + str(port) )
                scope.span.set_tag("key", argv[1])

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_kv({'message': e})
                scope.span.set_tag("error", True)
                ec = scope.span.tags.get('ec', 0)
                scope.span.set_tag("ec", ec+1)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper('asynqp.queue','Queue.get')
    def get_with_instana(wrapped, instance, argv, kwargs):
        parent_span = async_tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*argv, **kwargs)

        with async_tracer.start_active_span("rabbitmq", child_of=parent_span) as scope:
            host, port = instance.sender.protocol.transport._sock.getsockname()

            scope.span.set_tag("sort", "consume")
            scope.span.set_tag("address", host + ":" + str(port) )

            msg = yield from wrapped(*argv, **kwargs)

            if msg is not None:
                scope.span.set_tag("queue", instance.name)
                scope.span.set_tag("key", msg.routing_key)

            return msg

    @wrapt.patch_function_wrapper('asynqp.queue','Consumers.deliver')
    def deliver_with_instana(wrapped, instance, argv, kwargs):

        ctx = None
        msg = argv[1]
        if msg.headers is not None:
            ctx = async_tracer.extract(opentracing.Format.HTTP_HEADERS, dict(msg.headers))

        with async_tracer.start_active_span("rabbitmq", child_of=ctx) as scope:
            host, port = argv[1].sender.protocol.transport._sock.getsockname()

            try:
                scope.span.set_tag("exchange", msg.exchange_name)
                scope.span.set_tag("sort", "consume")
                scope.span.set_tag("address", host + ":" + str(port) )
                scope.span.set_tag("key", msg.routing_key)

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.log_kv({'message': e})
                scope.span.set_tag("error", True)
                ec = scope.span.tags.get('ec', 0)
                scope.span.set_tag("ec", ec+1)
                raise
            else:
                return rv

    logger.debug("Instrumenting asynqp")
except ImportError:
    pass
