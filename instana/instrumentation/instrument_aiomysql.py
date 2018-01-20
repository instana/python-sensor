from __future__ import absolute_import
import instana
import wrapt
import opentracing.ext.tags as ext

try:
    import instrument_aiomysql

    @wrapt.patch_function_wrapper('aiomysql','cursors.Cursor.execute')
    def connect_with_aiomysql(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()
        print("Instrumenting aiomysql")
        try:
            span = instana.internal_tracer.start_span("aiomysql", child_of=context)
            span.set_tag(ext.COMPONENT, "Database")
            span.set_tag(ext.COMPONENT, "aiomysql")
            span.set_tag(ext.SPAN_KIND, "Database")
            span.set_tag(ext.SPAN_KIND, "aiomysql")
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
    instana.log.debug("Instrumenting aiomysql")

except ImportError:
    pass