from __future__ import absolute_import

import opentracing
import wrapt

from ..log import logger
from ..singletons import async_tracer

try:
    import asynqp
    import asyncio

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
            async_tracer.inject(scope.span.context, opentracing.Format.TEXT_MAP, msg.headers)

            try:
                scope.span.set_tag("exchange", instance.name)
                scope.span.set_tag("sort", "publish")
                scope.span.set_tag("address", host + ":" + str(port) )

                if 'routing_key' in kwargs:
                    scope.span.set_tag("key", kwargs['routing_key'])
                elif len(argv) > 1 and argv[1] is not None:
                    scope.span.set_tag("key", argv[1])

                rv = wrapped(*argv, **kwargs)
            except Exception as e:
                scope.span.mark_as_errored({'message': e})
                raise
            else:
                return rv

    @asyncio.coroutine
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

    @asyncio.coroutine
    @wrapt.patch_function_wrapper('asynqp.queue','Queue.consume')
    def consume_with_instana(wrapped, instance, argv, kwargs):
        def callback_generator(original_callback):
            def callback_with_instana(*argv, **kwargs):
                ctx = None
                msg = argv[0]
                if msg.headers is not None:
                    ctx = async_tracer.extract(opentracing.Format.TEXT_MAP, dict(msg.headers))

                with async_tracer.start_active_span("rabbitmq", child_of=ctx) as scope:
                    host, port = msg.sender.protocol.transport._sock.getsockname()

                    try:
                        scope.span.set_tag("exchange", msg.exchange_name)
                        scope.span.set_tag("sort", "consume")
                        scope.span.set_tag("address", host + ":" + str(port) )
                        scope.span.set_tag("key", msg.routing_key)

                        original_callback(*argv, **kwargs)
                    except Exception as e:
                        scope.span.mark_as_errored({'message': e})
                        raise

            return callback_with_instana

        cb = argv[0]
        argv = (callback_generator(cb),)
        return wrapped(*argv, **kwargs)

    logger.debug("Instrumenting asynqp")
except ImportError:
    pass
