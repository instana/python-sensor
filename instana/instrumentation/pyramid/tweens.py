from __future__ import absolute_import

from pyramid.httpexceptions import HTTPException

import opentracing as ot
import opentracing.ext.tags as ext

from ...log import logger
from ...singletons import tracer, agent
from ...util import strip_secrets_from_query


class InstanaTweenFactory(object):
    """A factory that provides Instana instrumentation tween for Pyramid apps"""

    def __init__(self, handler, registry):
        self.handler = handler

    def __call__(self, request):
        ctx = tracer.extract(ot.Format.HTTP_HEADERS, dict(request.headers))
        scope = tracer.start_active_span('http', child_of=ctx)

        scope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
        scope.span.set_tag("http.host", request.host)
        scope.span.set_tag(ext.HTTP_METHOD, request.method)
        scope.span.set_tag(ext.HTTP_URL, request.path)

        if request.matched_route is not None:
            scope.span.set_tag("http.path_tpl", request.matched_route.pattern)

        if agent.options.extra_http_headers is not None:
            for custom_header in agent.options.extra_http_headers:
                # Headers are available in this format: HTTP_X_CAPTURE_THIS
                h = ('HTTP_' + custom_header.upper()).replace('-', '_')
                if h in request.headers:
                    scope.span.set_tag("http.%s" % custom_header, request.headers[h])

        if len(request.query_string):
            scrubbed_params = strip_secrets_from_query(request.query_string, agent.options.secrets_matcher, agent.options.secrets_list)
            scope.span.set_tag("http.params", scrubbed_params)

        response = None
        try:
            response = self.handler(request)

            tracer.inject(scope.span.context, ot.Format.HTTP_HEADERS, response.headers)
            response.headers['Server-Timing'] = "intid;desc=%s" % scope.span.context.trace_id
        except HTTPException as e:
            response = e
            raise
        except BaseException as e:
            scope.span.set_tag("http.status", 500)

            # we need to explicitly populate the `message` tag with an error here
            # so that it's picked up from an SDK span
            scope.span.set_tag("message", str(e))
            scope.span.log_exception(e)

            logger.debug("Pyramid Instana tween", exc_info=True)
        finally:
            if response:
                scope.span.set_tag("http.status", response.status_int)

                if 500 <= response.status_int <= 511:
                    if response.exception is not None:
                        message = str(response.exception)
                        scope.span.log_exception(response.exception)
                    else:
                        message = response.status

                    scope.span.set_tag("message", message)
                    scope.span.assure_errored()

            scope.close()

        return response


def includeme(config):
    logger.debug("Instrumenting pyramid")
    config.add_tween(__name__ + '.InstanaTweenFactory')
