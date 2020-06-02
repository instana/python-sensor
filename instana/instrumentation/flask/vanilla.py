from __future__ import absolute_import

import re
import flask

import opentracing
import opentracing.ext.tags as ext
import wrapt

from ...log import logger
from ...singletons import agent, tracer
from ...util import strip_secrets

path_tpl_re = re.compile('<.*>')


def before_request_with_instana(*argv, **kwargs):
    try:
        env = flask.request.environ
        ctx = None

        if 'HTTP_X_INSTANA_T' in env and 'HTTP_X_INSTANA_S' in env:
            ctx = tracer.extract(opentracing.Format.HTTP_HEADERS, env)

        flask.g.scope = tracer.start_active_span('wsgi', child_of=ctx)
        span = flask.g.scope.span

        if hasattr(agent, 'extra_headers') and agent.extra_headers is not None:
            for custom_header in agent.extra_headers:
                # Headers are available in this format: HTTP_X_CAPTURE_THIS
                header = ('HTTP_' + custom_header.upper()).replace('-', '_')
                if header in env:
                    span.set_tag("http.%s" % custom_header, env[header])

        span.set_tag(ext.HTTP_METHOD, flask.request.method)
        if 'PATH_INFO' in env:
            span.set_tag(ext.HTTP_URL, env['PATH_INFO'])
        if 'QUERY_STRING' in env and len(env['QUERY_STRING']):
            scrubbed_params = strip_secrets(env['QUERY_STRING'], agent.secrets_matcher, agent.secrets_list)
            span.set_tag("http.params", scrubbed_params)
        if 'HTTP_HOST' in env:
            span.set_tag("http.host", env['HTTP_HOST'])

        if hasattr(flask.request.url_rule, 'rule') and \
                path_tpl_re.search(flask.request.url_rule.rule) is not None:
            path_tpl = flask.request.url_rule.rule.replace("<", "{")
            path_tpl = path_tpl.replace(">", "}")
            span.set_tag("http.path_tpl", path_tpl)
    except:
        logger.debug("Flask before_request", exc_info=True)
    finally:
        return None


def after_request_with_instana(response):
    scope = None
    try:
        # If we're not tracing, just return
        if not hasattr(flask.g, 'scope'):
            return response

        scope = flask.g.scope
        if scope is not None:
            span = scope.span

            if 500 <= response.status_code <= 511:
                span.mark_as_errored()

            span.set_tag(ext.HTTP_STATUS_CODE, int(response.status_code))
            tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, response.headers)
            response.headers.add('Server-Timing', "intid;desc=%s" % scope.span.context.trace_id)
    except:
        logger.debug("Flask after_request", exc_info=True)
    finally:
        if scope is not None:
            scope.close()
            flask.g.scope = None
        return response


def teardown_request_with_instana(*argv, **kwargs):
    """
    In the case of exceptions, after_request_with_instana isn't called
    so we capture those cases here.
    """
    if hasattr(flask.g, 'scope') and flask.g.scope is not None:
        if len(argv) > 0 and argv[0] is not None:
            scope = flask.g.scope
            scope.span.log_exception(argv[0])
            if ext.HTTP_STATUS_CODE not in scope.span.tags:
                scope.span.set_tag(ext.HTTP_STATUS_CODE, 500)
        flask.g.scope.close()
        flask.g.scope = None


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
                if hasattr(response, 'code'):
                    status_code = response.code
                else:
                    status_code = response.status_code

                if 500 <= status_code <= 511:
                    span.log_exception(exc)

                span.set_tag(ext.HTTP_STATUS_CODE, int(status_code))

                if hasattr(response, 'headers'):
                    tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, response.headers)
                    if hasattr(response.headers, 'add'):
                        response.headers.add('Server-Timing', "intid;desc=%s" % scope.span.context.trace_id)
                    elif type(response.headers) is dict or hasattr(response.headers, "__dict__"):
                        response.headers['Server-Timing'] = "intid;desc=%s" % scope.span.context.trace_id

            scope.close()
            flask.g.scope = None
    except:
        logger.debug("handle_user_exception_with_instana:", exc_info=True)
    finally:
        return response


@wrapt.patch_function_wrapper('flask', 'Flask.full_dispatch_request')
def full_dispatch_request_with_instana(wrapped, instance, argv, kwargs):
    if not hasattr(instance, '_stan_wuz_here'):
        logger.debug("Flask(vanilla): Applying flask before/after instrumentation funcs")
        setattr(instance, "_stan_wuz_here", True)
        instance.after_request(after_request_with_instana)
        instance.before_request(before_request_with_instana)
        instance.teardown_request(teardown_request_with_instana)
    return wrapped(*argv, **kwargs)


logger.debug("Instrumenting flask (without blinker support)")
