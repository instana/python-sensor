# coding: utf-8

from __future__ import absolute_import

import wrapt
import opentracing
import pdb

from ..log import logger
from ..singletons import tracer

try:
    import pika

    def _extract_broker_tags(span, sort, conn, queue_or_routing_key, exchange=None):
        try:
            span.set_tag("address", "%s:%d" % (conn.params.host, conn.params.port))
            span.set_tag("sort", sort)
            span.set_tag("key", queue_or_routing_key)

            if exchange is not None:
                span.set_tag("exchange", exchange)
        except:
            logger.debug("_extract_consumer_tags: ", exc_info=True)

    def basic_publish_with_instana(wrapped, instance, args, kwargs):
        def _bind_args(exchange, routing_key, body, properties=None, *args, **kwargs):
            return (exchange, routing_key, body, properties, args, kwargs)

        parent_span = tracer.active_span

        if parent_span is None:
            return wrapped(*args, **kwargs)

        (exchange, routing_key, body, properties, args, kwargs) = (_bind_args(*args, **kwargs))

        with tracer.start_active_span("rabbitmq", child_of=parent_span) as scope:
            _extract_broker_tags(scope.span, "publish", instance.connection, routing_key, exchange=exchange)

            # context propagation
            properties = properties or pika.BasicProperties()
            properties.headers = properties.headers or {}

            tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, properties.headers)
            args = (exchange, routing_key, body, properties) + args

            try:
                rv = wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    def basic_get_with_instana(wrapped, instance, args, kwargs):
        def _bind_args(queue, callback, *args, **kwargs):
            return (queue, callback, args, kwargs)

        (queue, callback, args, kwargs) = (_bind_args(*args, **kwargs))

        def _cb_wrapper(channel, method, properties, body):
            parent_span = tracer.extract(opentracing.Format.HTTP_HEADERS, properties.headers)

            with tracer.start_active_span("rabbitmq", child_of=parent_span) as scope:
                _extract_broker_tags(scope.span, "consume", instance.connection, queue)

                try:
                    callback(channel, method, properties, body)
                except Exception as e:
                    scope.span.log_exception(e)
                    raise

        args = (queue, _cb_wrapper) + args
        return wrapped(*args, **kwargs)

    def basic_consume_with_instana(wrapped, instance, args, kwargs):
        def _bind_args(queue, on_consume_callback, *args, **kwargs):
            return (queue, on_consume_callback, args, kwargs)

        (queue, on_consume_callback, args, kwargs) = (_bind_args(*args, **kwargs))

        def _cb_wrapper(channel, method, properies, body):
            parent_span = tracer.extract(opentracing.Format.HTTP_HEADERS, properties.headers)

            with tracer.start_active_span("rabbitmq", child_of=parent_span) as scope:
                _extract_broker_tags(scope.span, "consume", instance.connection, queue)

                try:
                    callback(channel, method, properties, body)
                except Exception as e:
                    scope.span.log_exception(e)
                    raise

        args = (queue, _cb_wrapper) + args
        return wrapped(*args, **kwargs)

    wrapt.wrap_function_wrapper('pika.channel', 'Channel.basic_publish', basic_publish_with_instana)
    wrapt.wrap_function_wrapper('pika.channel', 'Channel.basic_get', basic_get_with_instana)
    wrapt.wrap_function_wrapper('pika.channel', 'Channel.basic_consume', basic_get_with_instana)

    logger.debug("Instrumenting pika")
except ImportError:
    pass
