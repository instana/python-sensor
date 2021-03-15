# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

from __future__ import absolute_import

import wrapt

from ..log import logger
from ..singletons import tracer

try:
    import redis

    EXCLUDED_PARENT_SPANS = ["redis", "celery-client", "celery-worker"]

    def collect_tags(span, instance, args, kwargs):
        try:
            ckw = instance.connection_pool.connection_kwargs

            span.set_tag("driver", "redis-py")

            host = ckw.get('host', None)
            port = ckw.get('port', '6379')
            db = ckw.get('db', None)

            if host is not None:
                url = "redis://%s:%s" % (host, port)
                if db is not None:
                    url = url + "/%s" % db
                span.set_tag('connection', url)

        except:
            logger.debug("redis.collect_tags non-fatal error", exc_info=True)
        finally:
            return span


    def execute_command_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None or parent_span.operation_name in EXCLUDED_PARENT_SPANS:
            return wrapped(*args, **kwargs)

        with tracer.start_active_span("redis", child_of=parent_span) as scope:
            try:
                collect_tags(scope.span, instance, args, kwargs)
                if (len(args) > 0):
                    scope.span.set_tag("command", args[0])

                rv = wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv


    def execute_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None or parent_span.operation_name in EXCLUDED_PARENT_SPANS:
            return wrapped(*args, **kwargs)

        with tracer.start_active_span("redis", child_of=parent_span) as scope:
            try:
                collect_tags(scope.span, instance, args, kwargs)
                scope.span.set_tag("command", 'PIPELINE')

                pipe_cmds = []
                for e in instance.command_stack:
                    pipe_cmds.append(e[0][0])
                scope.span.set_tag("subCommands", pipe_cmds)
            except Exception as e:
                # If anything breaks during K/V collection, just log a debug message
                logger.debug("Error collecting pipeline commands", exc_info=True)

            try:
                rv = wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    if redis.VERSION < (3,0,0):
        wrapt.wrap_function_wrapper('redis.client', 'BasePipeline.execute', execute_with_instana)
        wrapt.wrap_function_wrapper('redis.client', 'StrictRedis.execute_command', execute_command_with_instana)
    else:
        wrapt.wrap_function_wrapper('redis.client', 'Pipeline.execute', execute_with_instana)
        wrapt.wrap_function_wrapper('redis.client', 'Redis.execute_command', execute_command_with_instana)

        logger.debug("Instrumenting redis")
except ImportError:
    pass
