from __future__ import absolute_import
import instana
import wrapt
import opentracing.ext.tags as ext

try:
    import instrument_psycopg2

    @wrapt.patch_function_wrapper('psycopg2','connect')
    def connect_with_psycopg2(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()
        print("Instrumenting postgres psycopg2")
        try:
            span = instana.internal_tracer.start_span("postgres_connect", child_of=context)
            span.set_tag(ext.COMPONENT, "DatabaseConnect")
            span.set_tag(ext.SPAN_KIND, "cursor connect")
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
    instana.log.debug("Instrumenting postgres psycopg2")

except ImportError:
    pass


try:
    import instrument_psycopg2

    @wrapt.patch_function_wrapper('psycopg2.cursor','cursor.execute')
    def connect_with_psycopg2(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()
        print("Instrumenting postgres psycopg2")
        try:
            span = instana.internal_tracer.start_span("postgres_cursor", child_of=context)
            span.set_tag(ext.COMPONENT, "DatabaseCursor")
            span.set_tag(ext.SPAN_KIND, "cursor execute")
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
    instana.log.debug("Instrumenting postgres psycopg2")

except ImportError:
    pass