# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import opentracing
import wrapt

from ...log import logger
from ...singletons import agent, setup_tornado_tracer, tornado_tracer
from ...util.secrets import strip_secrets_from_query

try:
    import tornado

    # Tornado >=6.0 switched to contextvars for context management.  This requires changes to the opentracing
    # scope managers which we will tackle soon.
    # Limit Tornado version for the time being.
    if not (hasattr(tornado, 'version') and tornado.version[0] < '6'):
        logger.debug('Instana supports Tornado package versions < 6.0.  Skipping.')
        raise ImportError

    from opentracing.scope_managers.tornado import tracer_stack_context

    setup_tornado_tracer()

    def extract_custom_headers(span, headers):
        if not agent.options.extra_http_headers or not headers:
            return
        try:
            for custom_header in agent.options.extra_http_headers:
                if custom_header in headers:
                    span.set_tag("http.header.%s" % custom_header, headers[custom_header])

        except Exception:
            logger.debug("extract_custom_headers: ", exc_info=True)


    @wrapt.patch_function_wrapper('tornado.web', 'RequestHandler._execute')
    def execute_with_instana(wrapped, instance, argv, kwargs):
        try:
            with tracer_stack_context():
                ctx = None
                if hasattr(instance.request.headers, '__dict__') and '_dict' in instance.request.headers.__dict__:
                    ctx = tornado_tracer.extract(opentracing.Format.HTTP_HEADERS,
                                                 instance.request.headers.__dict__['_dict'])
                scope = tornado_tracer.start_active_span('tornado-server', child_of=ctx)

                # Query param scrubbing
                if instance.request.query is not None and len(instance.request.query) > 0:
                    cleaned_qp = strip_secrets_from_query(instance.request.query, agent.options.secrets_matcher,
                                                          agent.options.secrets_list)
                    scope.span.set_tag("http.params", cleaned_qp)

                url = "%s://%s%s" % (instance.request.protocol, instance.request.host, instance.request.path)
                scope.span.set_tag("http.url", url)
                scope.span.set_tag("http.method", instance.request.method)

                scope.span.set_tag("handler", instance.__class__.__name__)

                # Request header tracking support
                extract_custom_headers(scope.span, instance.request.headers)

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

            with instance.request._instana as scope:
                # Response header tracking support
                extract_custom_headers(scope.span, instance._headers)

                status_code = instance.get_status()

                # Mark 500 responses as errored
                if 500 <= status_code:
                    scope.span.mark_as_errored()

                scope.span.set_tag("http.status_code", status_code)

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
