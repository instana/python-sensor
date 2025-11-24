# (c) Copyright IBM Corp. 2021, 2025
# (c) Copyright Instana Inc. 2019


import re
from importlib.metadata import version
from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple, Type, Union

import flask
import wrapt
from opentelemetry import context, trace
from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent, get_tracer
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import extract_custom_headers

if TYPE_CHECKING:
    from flask.typing import ResponseReturnValue
    from jinja2.environment import Template
    from werkzeug.exceptions import HTTPException

path_tpl_re = re.compile("<.*>")


@wrapt.patch_function_wrapper("flask", "templating._render")
def render_with_instana(
    wrapped: Callable[..., str],
    instance: object,
    argv: Tuple[flask.app.Flask, "Template", Dict[str, Any]],
    kwargs: Dict[str, Any],
) -> str:
    # If we're not tracing, just return
    if not (hasattr(flask, "g") and hasattr(flask.g, "span")):
        return wrapped(*argv, **kwargs)

    parent_span = flask.g.span
    parent_context = parent_span.get_span_context()
    tracer = get_tracer()

    with tracer.start_as_current_span("render", span_context=parent_context) as span:
        try:
            flask_version = tuple(map(int, version("flask").split(".")))
            template = argv[1] if flask_version >= (2, 2, 0) else argv[0]

            span.set_attribute("type", "template")
            if template.name is None:
                span.set_attribute("name", "(from string)")
            else:
                span.set_attribute("name", template.name)

            return wrapped(*argv, **kwargs)
        except Exception as e:
            span.record_exception(e)
            raise


@wrapt.patch_function_wrapper("flask", "Flask.handle_user_exception")
def handle_user_exception_with_instana(
    wrapped: Callable[..., Union["HTTPException", "ResponseReturnValue"]],
    instance: flask.app.Flask,
    argv: Tuple[Exception],
    kwargs: Dict[str, Any],
) -> Union["HTTPException", "ResponseReturnValue"]:
    # Call original and then try to do post processing
    response = wrapped(*argv, **kwargs)

    try:
        exc = argv[0]

        if hasattr(flask.g, "span") and flask.g.span:
            span = flask.g.span

            if response:
                if isinstance(response, tuple):
                    status_code = response[1]
                else:
                    if hasattr(response, "code"):
                        status_code = response.code
                    else:
                        status_code = response.status_code

                if 500 <= status_code:
                    span.record_exception(exc)

                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, int(status_code))

                if hasattr(response, "headers"):
                    tracer = get_tracer()
                    tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)
            if span and span.is_recording():
                span.end()
            flask.g.span = None
    except Exception:
        logger.debug("handle_user_exception_with_instana:", exc_info=True)

    return response


def create_span():
    env = flask.request.environ
    tracer = get_tracer()
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


def inject_span(
    response: flask.wrappers.Response,
    error_message: str,
    set_flask_g_none: bool = False,
):
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
            tracer = get_tracer()
            tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)
    except Exception:
        logger.debug(error_message, exc_info=True)
    finally:
        if span and span.is_recording():
            span.end()
            if set_flask_g_none:
                flask.g.span = None


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
