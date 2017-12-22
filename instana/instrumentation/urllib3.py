import opentracing.ext.tags as ext
import opentracing
import wrapt


@wrapt.patch_function_wrapper('urllib3', 'PoolManager.urlopen')
def urlopen_with_instana(wrapped, instance, args, kwargs):
    try:
        span = opentracing.global_tracer.start_span("urllib3")
        span.set_tag(ext.HTTP_URL, args[1])
        span.set_tag(ext.HTTP_METHOD, args[0])

        opentracing.global_tracer.inject(span.context, opentracing.Format.HTTP_HEADERS, kwargs["headers"])

        rv = wrapped(*args, **kwargs)
        span.set_tag(ext.HTTP_STATUS_CODE, rv.status)
        if 500 <= rv.status <= 511:
            span.set_tag("error", True)
            ec = span.tags.get('ec', 0)
            span.set_tag("ec", ec+1)

    except Exception as e:
        print("found error:", e)
        span.set_tag("error", True)
        ec = span.tags.get('ec', 0)
        span.set_tag("ec", ec+1)
        raise
    else:
        span.finish()
        return rv
