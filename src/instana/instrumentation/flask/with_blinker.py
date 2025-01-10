# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import re
import wrapt
from typing import Any, Tuple, Dict, Callable

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry import context, trace

from instana.log import logger
from instana.util.secrets import strip_secrets_from_query
from instana.singletons import agent, tracer
from instana.util.traceutils import extract_custom_headers
from instana.propagators.format import Format

import flask
from flask import request_started, request_finished, got_request_exception

path_tpl_re = re.compile("<.*>")


def request_started_with_instana(sender: flask.app.Flask, **extra: Any) -> None:
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
        logger.debug("Flask request_started_with_instana", exc_info=True)


def request_finished_with_instana(
    sender: flask.app.Flask, response: flask.wrappers.Response, **extra: Any
) -> None:
    span = None
    try:
        if not hasattr(flask.g, "span"):
            return

        span = flask.g.span
        if span:
            if 500 <= response.status_code:
                span.mark_as_errored()

            span.set_attribute(
                SpanAttributes.HTTP_STATUS_CODE, int(response.status_code)
            )
            extract_custom_headers(span, response.headers, format=False)

            tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)
    except Exception:
        logger.debug("Flask request_finished_with_instana", exc_info=True)
    finally:
        if span and span.is_recording():
            span.end()


def log_exception_with_instana(
    sender: flask.app.Flask, exception: Exception, **extra: Any
) -> None:
    if hasattr(flask.g, "span") and flask.g.span:
        span = flask.g.span
        if span:
            span.record_exception(exception)
            # As of Flask 2.3.x:
            # https://github.com/pallets/flask/blob/
            # d0bf462866289ad8bfe29b6e4e1e0f531003ab34/src/flask/app.py#L1379
            # The `got_request_exception` signal, is only sent by
            # the `handle_exception` method which "always causes a 500"
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 500)
            if span.is_recording():
                span.end()


def teardown_request_with_instana(*argv: Any, **kwargs: Any) -> None:
    """
    In the case of exceptions, request_finished_with_instana isn't called
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


@wrapt.patch_function_wrapper("flask", "Flask.full_dispatch_request")
def full_dispatch_request_with_instana(
    wrapped: Callable[..., flask.wrappers.Response],
    instance: flask.app.Flask,
    argv: Tuple,
    kwargs: Dict,
) -> flask.wrappers.Response:
    if not hasattr(instance, "_stan_wuz_here"):
        logger.debug(
            "Flask(blinker): Applying flask before/after instrumentation funcs"
        )
        setattr(instance, "_stan_wuz_here", True)
        got_request_exception.connect(log_exception_with_instana, instance)
        request_started.connect(request_started_with_instana, instance)
        request_finished.connect(request_finished_with_instana, instance)
        instance.teardown_request(teardown_request_with_instana)

    return wrapped(*argv, **kwargs)


logger.debug("Instrumenting flask (with blinker support)")
