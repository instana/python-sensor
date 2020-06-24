from __future__ import absolute_import

import wrapt
import flask
import opentracing
import opentracing.ext.tags as ext

from ...log import logger
from ...singletons import tracer


@wrapt.patch_function_wrapper('flask', 'templating._render')
def render_with_instana(wrapped, instance, argv, kwargs):
    ctx = argv[1]

    # If we're not tracing, just return
    if not hasattr(ctx['g'], 'scope'):
        return wrapped(*argv, **kwargs)

    with tracer.start_active_span("render", child_of=ctx['g'].scope.span) as rscope:
        try:
            template = argv[0]

            rscope.span.set_tag("type", "template")
            if template.name is None:
                rscope.span.set_tag("name", '(from string)')
            else:
                rscope.span.set_tag("name", template.name)

            return wrapped(*argv, **kwargs)
        except Exception as e:
            rscope.span.log_exception(e)
            raise


@wrapt.patch_function_wrapper('flask', 'Flask.handle_user_exception')
def handle_user_exception_with_instana(wrapped, instance, argv, kwargs):
    # Call original and then try to do post processing
    response = wrapped(*argv, **kwargs)

    try:
        exc = argv[0]

        if hasattr(flask.g, 'scope') and flask.g.scope is not None:
            scope = flask.g.scope
            span = scope.span

            if response is not None:
                if isinstance(response, tuple):
                    status_code = response[1]
                else:
                    if hasattr(response, 'code'):
                        status_code = response.code
                    else:
                        status_code = response.status_code

                if 500 <= status_code <= 511:
                    span.log_exception(exc)

                span.set_tag(ext.HTTP_STATUS_CODE, int(status_code))

                if hasattr(response, 'headers'):
                    tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, response.headers)
                    value = "intid;desc=%s" % scope.span.context.trace_id
                    if hasattr(response.headers, 'add'):
                        response.headers.add('Server-Timing', value)
                    elif type(response.headers) is dict or hasattr(response.headers, "__dict__"):
                        response.headers['Server-Timing'] = value

            scope.close()
            flask.g.scope = None
    except:
        logger.debug("handle_user_exception_with_instana:", exc_info=True)
    finally:
        return response
