from __future__ import absolute_import

import opentracing
import wrapt

from ...log import logger
from ...singletons import agent, setup_tornado_tracer, tornado_tracer
from ...util import strip_secrets

from distutils.version import LooseVersion

try:
    import tornado
    from opentracing.scope_managers.tornado import tracer_stack_context

    setup_tornado_tracer()

    # Tornado >=6.0 switched to contextvars for context management.  This requires changes to the opentracing
    # scope managers which we will tackle soon.
    # Limit Tornado version for the time being.
    if hasattr(tornado, 'version') and (LooseVersion(tornado.version) < LooseVersion('6.0.0')):

        @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler._execute')
        def execute_with_instana(wrapped, instance, argv, kwargs):
            try:
                with tracer_stack_context():
                    ctx = tornado_tracer.extract(opentracing.Format.HTTP_HEADERS, instance.request.headers)
                    scope = tornado_tracer.start_active_span('tornado-server', child_of=ctx)

                    # Query param scrubbing
                    if instance.request.query is not None and len(instance.request.query) > 0:
                        cleaned_qp = strip_secrets(instance.request.query, agent.secrets_matcher, agent.secrets_list)
                        scope.span.set_tag("http.params", cleaned_qp)

                    url = "%s://%s%s" % (instance.request.protocol, instance.request.host, instance.request.path)
                    scope.span.set_tag("http.url", url)
                    scope.span.set_tag("http.method", instance.request.method)

                    scope.span.set_tag("handler", instance.__class__.__name__)

                    # Custom header tracking support
                    if agent.extra_headers is not None:
                        for custom_header in agent.extra_headers:
                            if custom_header in instance.request.headers:
                                scope.span.set_tag("http.%s" % custom_header, instance.request.headers[custom_header])

                    setattr(instance.request, "_instana", scope)

                    # Set the context response headers now because tornado doesn't give us a better option to do so
                    # later for this request.
                    tornado_tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, instance._headers)
                    instance.set_header(name='Server-Timing', value="intid;desc=%s" % scope.span.context.trace_id)

                    return wrapped(*argv, **kwargs)
            except Exception:
                logger.debug("tornado execute", exc_info=True)


        @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler.set_default_headers')
        def set_default_headers_with_instana(wrapped, instance, argv, kwargs):
            if not hasattr(instance.request, '_instana'):
                return wrapped(*argv, **kwargs)

            scope = instance.request._instana
            tornado_tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, instance._headers)
            instance.set_header(name='Server-Timing', value="intid;desc=%s" % scope.span.context.trace_id)


        @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler.on_finish')
        def on_finish_with_instana(wrapped, instance, argv, kwargs):
            try:
                if not hasattr(instance.request, '_instana'):
                    return wrapped(*argv, **kwargs)

                scope = instance.request._instana
                status_code = instance.get_status()

                # Mark 500 responses as errored
                if 500 <= status_code <= 511:
                    scope.span.set_tag("error", True)
                    ec = scope.span.tags.get('ec', 0)
                    if ec is 0:
                        scope.span.set_tag("ec", ec + 1)

                scope.span.set_tag("http.status_code", status_code)
                scope.close()

                return wrapped(*argv, **kwargs)
            except Exception:
                logger.debug("tornado on_finish", exc_info=True)

        @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler.log_exception')
        def log_exception_with_instana(wrapped, instance, argv, kwargs):
            try:
                if not hasattr(instance.request, '_instana'):
                    return wrapped(*argv, **kwargs)

                if not isinstance(argv[1], tornado.web.HTTPError):
                    scope = instance.request._instana
                    scope.span.log_exception(argv[0])

                return wrapped(*argv, **kwargs)
            except Exception:
                logger.debug("tornado log_exception", exc_info=True)

        logger.debug("Instrumenting tornado server")
except ImportError:
    pass

