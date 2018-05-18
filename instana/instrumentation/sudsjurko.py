from __future__ import absolute_import
import instana
from instana.log import logger
import opentracing
import opentracing.ext.tags as ext
import wrapt


try:
    import suds # noqa

    # previously named SoapClient
    @wrapt.patch_function_wrapper('suds.client', '_SoapClient.send')
    def send_with_instana(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()

        # If we're not tracing, just return
        if context is None:
            return wrapped(*args, **kwargs)

        try:
            span = instana.internal_tracer.start_span("soap", child_of=context)
            span.set_tag('soap.action', instance.method.name)
            span.set_tag(ext.HTTP_URL, instance.method.location)

            instana.internal_tracer.inject(span.context, opentracing.Format.HTTP_HEADERS,
                                           instance.options.headers)

            rv = wrapped(*args, **kwargs)

        except Exception as e:
            span.log_kv({'message': e})
            span.set_tag("error", True)
            ec = span.tags.get('ec', 0)
            span.set_tag("ec", ec+1)
            raise
        else:
            return rv
        finally:
            span.finish()

    instana.log.debug("Instrumenting suds-jurko")
except ImportError:
    pass
