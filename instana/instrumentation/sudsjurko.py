from __future__ import absolute_import
import instana
from instana.log import logger
import opentracing
import opentracing.ext.tags as ext
import wrapt


try:
    import suds # noqa

    if (suds.version.__version__ <= '0.6'):
        class_method = 'SoapClient.send'
    else:
        class_method = '_SoapClient.send'

    @wrapt.patch_function_wrapper('suds.client', class_method)
    def send_with_instana(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()

        # If we're not tracing, just return
        if context is None:
            return wrapped(*args, **kwargs)

        try:
            span = instana.internal_tracer.start_span("soap", child_of=context)
            span.set_tag('soap.action', instance.method.name)
            span.set_tag(ext.HTTP_URL, instance.method.location)
            span.set_tag(ext.HTTP_METHOD, 'POST')

            instana.internal_tracer.inject(span.context, opentracing.Format.HTTP_HEADERS,
                                           instance.options.headers)

            rv = wrapped(*args, **kwargs)

        except Exception as e:
            span.log_exception(e)
            span.set_tag(ext.HTTP_STATUS_CODE, 500)
            raise
        else:
            span.set_tag(ext.HTTP_STATUS_CODE, 200)
            return rv
        finally:
            span.finish()

    logger.debug("Instrumenting suds-jurko")
except ImportError:
    pass
