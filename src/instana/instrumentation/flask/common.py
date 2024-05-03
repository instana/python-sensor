# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import wrapt
import flask
import opentracing
import opentracing.ext.tags as ext

from ...log import logger
from ...singletons import tracer, agent


@wrapt.patch_function_wrapper('flask', 'templating._render')
def render_with_instana(wrapped, instance, argv, kwargs):
    # If we're not tracing, just return
    if not (hasattr(flask, 'g') and hasattr(flask.g, 'scope')):
        return wrapped(*argv, **kwargs)

    parent_span = flask.g.scope.span

    with tracer.start_active_span("render", child_of=parent_span) as rscope:
        try:
            flask_version = tuple(map(int, flask.__version__.split('.')))
            template = argv[1] if flask_version >= (2, 2, 0) else argv[0]

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

                if 500 <= status_code:
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

    return response


def extract_custom_headers(span, headers, format):
    if agent.options.extra_http_headers is None:
        return
    try:
        for custom_header in agent.options.extra_http_headers:
            # Headers are available in this format: HTTP_X_CAPTURE_THIS
            flask_header = ('HTTP_' + custom_header.upper()).replace('-', '_') if format else custom_header
            if flask_header in headers:
                span.set_tag("http.header.%s" % custom_header, headers[flask_header])

    except Exception:
        logger.debug("extract_custom_headers: ", exc_info=True)
