from __future__ import absolute_import

import opentracing
import opentracing.ext.tags as ext
import wrapt

from ..log import logger
from ..singletons import tracer

try:
    import redis

    @wrapt.patch_function_wrapper('redis.client','StrictRedis.execute_command')
    def execute_command_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # import ipdb; ipdb.set_trace()

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
                scope.span.log_kv({'message': e})
                scope.span.set_tag("error", True)
                ec = scope.span.tags.get('ec', 0)
                scope.span.set_tag("ec", ec+1)
                raise
            else:
                return rv

    logger.debug("Instrumenting redis")
except ImportError:
    pass
