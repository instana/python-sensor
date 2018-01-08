from __future__ import absolute_import
import opentracing.ext.tags as ext
import instana
import opentracing
import wrapt


try:
    import urllib3

    @wrapt.patch_function_wrapper('urllib3', 'PoolManager.urlopen')
    def urlopen_with_instana(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()

        # If we're not tracing, just return
        if context is None:
            return wrapped(*args, **kwargs)

        try:
            span = instana.internal_tracer.start_span("urllib3", child_of=context)
            span.set_tag(ext.HTTP_URL, args[1])
            span.set_tag(ext.HTTP_METHOD, args[0])

            instana.internal_tracer.inject(span.context, opentracing.Format.HTTP_HEADERS, kwargs["headers"])
            rv = wrapped(*args, **kwargs)

            span.set_tag(ext.HTTP_STATUS_CODE, rv.status)
            if 500 <= rv.status <= 599:
                span.set_tag("error", True)
                ec = span.tags.get('ec', 0)
                span.set_tag("ec", ec+1)

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

    instana.log.debug("Instrumenting urllib3")
except ImportError:
    pass
