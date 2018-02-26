from __future__ import absolute_import
import instana
import wrapt
import opentracing.ext.tags as ext



try:
    import instrumentation
    print("Initializing Redis Instrumentation")

    @wrapt.patch_function_wrapper('redis','StrictRedis.execute_command')
    def connect_with_aioredis(wrapped, instance, args, kwargs):
        wrappedfunction = str(wrapped)
        myinstance = str(instance.__class__)
        print(wrappedfunction)
        print(myinstance)
        #rdiskeys = instance.keys()
        context = instana.internal_tracer.current_context()
        try:
            span = instana.internal_tracer.start_span("redis", child_of=context)
            span.set_tag("kind", "exit")
            span.set_tag("db.instance", "127.0.0.1:6379" )
            span.set_tag("db.statement","GET mapcache-prod:Marcel:MarcelParis:drivers")
            span.set_tag("db.type", "redis" )
#            span.set_tag("peer.service", "localhost:6379")
            rv = wrapped(*args, **kwargs)

        except Exception as e:
            span.log_kv({'message': e})
            span.set_tag("error", True)
            ec = span.tags.get('ec', 0)
            span.set_tag("ec", ec+1)
            span.finish()
            raise
        else:
            span.finish()
            return rv
    instana.log.debug("Instrumenting redis s")

except ImportError:
    pass

