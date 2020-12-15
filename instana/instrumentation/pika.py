# coding: utf-8

from __future__ import absolute_import

import wrapt
import opentracing
import pdb

from ..log import logger
from ..singletons import tracer

try:
    import pika

    def _bind_publish_args(exchange, routing_key, body, properties=None, *args, **kwargs):
        return (exchange, routing_key, body, properties, args, kwargs)

    def basic_publish_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        if parent_span is None:
            return wrapped(*args, **kwargs)

        (exchange, routing_key, body, properties, args, kwargs) = (_bind_publish_args(*args, **kwargs))

        with tracer.start_active_span("rabbitmq", child_of=parent_span) as scope:
            try:
                conn = instance.connection.params

                scope.span.set_tag("address", "%s:%d" % (conn.host, conn.port))
                scope.span.set_tag("sort", "publish")
                scope.span.set_tag("exchange", exchange)
                scope.span.set_tag("key", routing_key)
            except:
                logger.debug("basic_publish_with_instana: ", exc_info=True)

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

    def _bind_get_args(queue, callback, *args, **kwargs):
        return (queue, callback, args, kwargs)

    def basic_get_with_instana(wrapped, instance, args, kwargs):
        (queue, callback, args, kwargs) = (_bind_get_args(*args, **kwargs))

        def _cb_wrapper(channel, method, properties, body):
            parent_span = tracer.extract(opentracing.Format.HTTP_HEADERS, properties.headers)
            conn = channel.connection.params

            with tracer.start_active_span("rabbitmq", child_of=parent_span) as scope:
                try:
                    conn = instance.connection.params

                    scope.span.set_tag("address", "%s:%d" % (conn.host, conn.port))
                    scope.span.set_tag("sort", "consume")
                    scope.span.set_tag("key", queue)
                except:
                    logger.debug("basic_get_with_instana: ", exc_info=True)

                try:
                    callback(channel, method, properties, body)
                except Exception as e:
                    scope.span.log_exception(e)
                    raise

        args = (queue, _cb_wrapper) + args
        return wrapped(*args, **kwargs)

    wrapt.wrap_function_wrapper('pika.channel', 'Channel.basic_publish', basic_publish_with_instana)
    wrapt.wrap_function_wrapper('pika.channel', 'Channel.basic_get', basic_get_with_instana)

    logger.debug("Instrumenting pika")
except ImportError:
    pass
