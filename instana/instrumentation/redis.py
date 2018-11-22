from __future__ import absolute_import

import wrapt

from ..log import logger
from ..singletons import tracer

try:
    import redis

    if redis.VERSION < (3, 0, 0):

        @wrapt.patch_function_wrapper('redis.client','StrictRedis.execute_command')
        def execute_command_with_instana(wrapped, instance, args, kwargs):
            parent_span = tracer.active_span

            # If we're not tracing, just return
            if parent_span is None:
                return wrapped(*args, **kwargs)

            with tracer.start_active_span("redis", child_of=parent_span) as scope:

                try:
                    ckw = instance.connection_pool.connection_kwargs
                    url = "redis://%s:%d/%d" % (ckw['host'], ckw['port'], ckw['db'])
                    scope.span.set_tag("connection", url)
                    scope.span.set_tag("driver", "redis-py")
                    scope.span.set_tag("command", args[0])

                    rv = wrapped(*args, **kwargs)
                except Exception as e:
                    scope.span.set_tag("redis.error", str(e))
                    scope.span.set_tag("error", True)
                    ec = scope.span.tags.get('ec', 0)
                    scope.span.set_tag("ec", ec+1)
                    raise
                else:
                    return rv

        @wrapt.patch_function_wrapper('redis.client','BasePipeline.execute')
        def execute_with_instana(wrapped, instance, args, kwargs):
            parent_span = tracer.active_span

            # If we're not tracing, just return
            if parent_span is None:
                return wrapped(*args, **kwargs)

            with tracer.start_active_span("redis", child_of=parent_span) as scope:

                try:
                    ckw = instance.connection_pool.connection_kwargs
                    url = "redis://%s:%d/%d" % (ckw['host'], ckw['port'], ckw['db'])
                    scope.span.set_tag("connection", url)
                    scope.span.set_tag("driver", "redis-py")
                    scope.span.set_tag("command", 'PIPELINE')

                    try:
                        pipe_cmds = []
                        for e in instance.command_stack:
                            pipe_cmds.append(e[0][0])
                        scope.span.set_tag("subCommands", pipe_cmds)
                    except Exception as e:
                        # If anything breaks during cmd collection, just log a
                        # debug message
                        logger.debug("Error collecting pipeline commands")

                    rv = wrapped(*args, **kwargs)
                except Exception as e:
                    scope.span.set_tag("redis.error", str(e))
                    scope.span.set_tag("error", True)
                    ec = scope.span.tags.get('ec', 0)
                    scope.span.set_tag("ec", ec+1)
                    raise
                else:
                    return rv

        logger.debug("Instrumenting redis")
    else:
        logger.debug("redis >=3.0.0 not supported (yet)")
except ImportError:
    pass
