from __future__ import absolute_import

from distutils.version import LooseVersion

import opentracing
import opentracing.ext.tags as ext
import wrapt

from ..log import logger
from ..singletons import tracer

try:
    import suds # noqa

    if (LooseVersion(suds.version.__version__) <= LooseVersion('0.6')):
        class_method = 'SoapClient.send'
    else:
        class_method = '_SoapClient.send'

    @wrapt.patch_function_wrapper('suds.client', class_method)
    def send_with_instana(wrapped, instance, args, kwargs):
        parent_span = tracer.active_span

        # If we're not tracing, just return
        if parent_span is None:
            return wrapped(*args, **kwargs)

        with tracer.start_active_span("soap", child_of=parent_span) as scope:
            try:
                scope.span.set_tag('soap.action', instance.method.name)
                scope.span.set_tag(ext.HTTP_URL, instance.method.location)
                scope.span.set_tag(ext.HTTP_METHOD, 'POST')

                tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, instance.options.headers)

                rv = wrapped(*args, **kwargs)

            except Exception as e:
                scope.span.log_exception(e)
                scope.span.set_tag(ext.HTTP_STATUS_CODE, 500)
                raise
            else:
                scope.span.set_tag(ext.HTTP_STATUS_CODE, 200)
                return rv

    logger.debug("Instrumenting suds-jurko")
except ImportError:
    pass
