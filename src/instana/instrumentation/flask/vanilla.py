# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import re
import flask
import wrapt
from typing import Callable, Tuple, Dict, Type, Union

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry import context, trace

from instana.log import logger
from instana.singletons import agent, tracer
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import extract_custom_headers
from instana.propagators.format import Format

path_tpl_re = re.compile('<.*>')


def before_request_with_instana() -> None:
    try:
        env = flask.request.environ
        span_context = tracer.extract(Format.HTTP_HEADERS, env)

        span = tracer.start_span("wsgi", span_context=span_context)
        flask.g.span = span

        ctx = trace.set_span_in_context(span)
        token = context.attach(ctx)
        flask.g.token = token

        extract_custom_headers(span, env, format=True)

        span.set_attribute(SpanAttributes.HTTP_METHOD, flask.request.method)
        if "PATH_INFO" in env:
            span.set_attribute(SpanAttributes.HTTP_URL, env["PATH_INFO"])
        if "QUERY_STRING" in env and len(env["QUERY_STRING"]):
            scrubbed_params = strip_secrets_from_query(
                env["QUERY_STRING"],
                agent.options.secrets_matcher,
                agent.options.secrets_list,
            )
            span.set_attribute("http.params", scrubbed_params)
        if "HTTP_HOST" in env:
            span.set_attribute("http.host", env["HTTP_HOST"])

        if hasattr(flask.request.url_rule, "rule") and path_tpl_re.search(
            flask.request.url_rule.rule
        ):
            path_tpl = flask.request.url_rule.rule.replace("<", "{")
            path_tpl = path_tpl.replace(">", "}")
            span.set_attribute("http.path_tpl", path_tpl)
    except:
        logger.debug("Flask before_request", exc_info=True)

    return None


def after_request_with_instana(
    response: flask.wrappers.Response,
) -> flask.wrappers.Response:
    span = None
    try:
        # If we're not tracing, just return
        if not hasattr(flask.g, "span"):
            return response

        span = flask.g.span
        if span:

            if 500 <= response.status_code:
                span.mark_as_errored()

            span.set_attribute(
                SpanAttributes.HTTP_STATUS_CODE, int(response.status_code)
            )
            extract_custom_headers(span, response.headers, format=False)

            tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)
    except:
        logger.debug("Flask after_request", exc_info=True)
    finally:
        if span and span.is_recording():
            span.end()
            flask.g.span = None
    return response


def teardown_request_with_instana(*argv: Union[Exception, Type[Exception]]) -> None:
    """
    In the case of exceptions, after_request_with_instana isn't called
    so we capture those cases here.
    """
    if hasattr(flask.g, "span") and flask.g.span:
        if len(argv) > 0 and argv[0]:
            span = flask.g.span
            span.record_exception(argv[0])
            if SpanAttributes.HTTP_STATUS_CODE not in span.attributes:
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 500)
        if flask.g.span.is_recording():
            flask.g.span.end()
        flask.g.span = None

    if hasattr(flask.g, "token") and flask.g.token:
        context.detach(flask.g.token)
        flask.g.token = None


@wrapt.patch_function_wrapper('flask', 'Flask.full_dispatch_request')
def full_dispatch_request_with_instana(
    wrapped: Callable[..., flask.wrappers.Response],
    instance: flask.app.Flask,
    argv: Tuple,
    kwargs: Dict,
) -> flask.wrappers.Response:
    if not hasattr(instance, '_stan_wuz_here'):
        logger.debug("Flask(vanilla): Applying flask before/after instrumentation funcs")
        setattr(instance, "_stan_wuz_here", True)
        instance.before_request(before_request_with_instana)
        instance.after_request(after_request_with_instana)
        instance.teardown_request(teardown_request_with_instana)
    return wrapped(*argv, **kwargs)


logger.debug("Instrumenting flask (without blinker support)")
