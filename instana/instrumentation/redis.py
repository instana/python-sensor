from __future__ import absolute_import

import wrapt

from ..log import logger
from ..singletons import tracer

try:
    import redis

    if ((redis.VERSION >= (2, 10, 6)) and (redis.VERSION < (3, 0, 0))):

        def collect_tags(span, instance, args, kwargs):
            try:
                ckw = instance.connection_pool.connection_kwargs

                span.set_tag("driver", "redis-py")

                host = ckw.get('host', None)
                port = ckw.get('port', '6379')
                db = ckw.get('db',   None)

                if host is not None:
                    url = "redis://%s:%s" % (host, port)
                    if db is not None:
                        url = url + "/%s" % db
                    span.set_tag('connection', url)

            except:
                logger.debug("redis.collect_tags non-fatal error", exc_info=True)
            finally:
                return span

        @wrapt.patch_function_wrapper('redis.client','StrictRedis.execute_command')
        def execute_command_with_instana(wrapped, instance, args, kwargs):
            parent_span = tracer.active_span

            # If we're not tracing, just return
            if parent_span is None or parent_span.operation_name == "redis":
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

        @wrapt.patch_function_wrapper('redis.client','BasePipeline.execute')
        def execute_with_instana(wrapped, instance, args, kwargs):
            parent_span = tracer.active_span

            # If we're not tracing, just return
            if parent_span is None or parent_span.operation_name == "redis":
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

        logger.debug("Instrumenting redis")
    else:
        logger.debug("redis <= 2.10.5 >=3.0.0 not supported.")
        logger.debug("  --> https://docs.instana.io/ecosystem/python/supported-versions/#tracing")
except ImportError:
    pass
