# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

from __future__ import absolute_import
import wrapt

import opentracing as ot
import opentracing.ext.tags as tags

from ..log import logger
from ..singletons import agent, tracer
from ..util.secrets import strip_secrets_from_query


try:
    import webapp2

    logger.debug("Instrumenting webapp2")

    @wrapt.patch_function_wrapper('webapp2', 'WSGIApplication.__call__')
    def call_with_instana(wrapped, instance, argv, kwargs):
        env = argv[0]
        start_response = argv[1]

        def new_start_response(status, headers, exc_info=None):
            """Modified start response with additional headers."""
            if 'stan_scope' in env:
                scope = env['stan_scope']
                tracer.inject(scope.span.context, ot.Format.HTTP_HEADERS, headers)
                headers.append(('Server-Timing', "intid;desc=%s" % scope.span.context.trace_id))

                res = start_response(status, headers, exc_info)

                sc = status.split(' ')[0]
                if 500 <= int(sc) <= 511:
                    scope.span.mark_as_errored()

                scope.span.set_tag(tags.HTTP_STATUS_CODE, sc)
                scope.close()
                return res
            else:
                return start_response(status, headers, exc_info)

        ctx = tracer.extract(ot.Format.HTTP_HEADERS, env)
        scope = env['stan_scope'] = tracer.start_active_span("wsgi", child_of=ctx)

        if agent.options.extra_http_headers is not None:
            for custom_header in agent.options.extra_http_headers:
                # Headers are available in this format: HTTP_X_CAPTURE_THIS
                wsgi_header = ('HTTP_' + custom_header.upper()).replace('-', '_')
                if wsgi_header in env:
                    scope.span.set_tag("http.header.%s" % custom_header, env[wsgi_header])

        if 'PATH_INFO' in env:
            scope.span.set_tag('http.path', env['PATH_INFO'])
        if 'QUERY_STRING' in env and len(env['QUERY_STRING']):
            scrubbed_params = strip_secrets_from_query(env['QUERY_STRING'], agent.options.secrets_matcher, agent.options.secrets_list)
            scope.span.set_tag("http.params", scrubbed_params)
        if 'REQUEST_METHOD' in env:
            scope.span.set_tag(tags.HTTP_METHOD, env['REQUEST_METHOD'])
        if 'HTTP_HOST' in env:
            scope.span.set_tag("http.host", env['HTTP_HOST'])

        return wrapped(env, new_start_response)
except ImportError:
    pass
