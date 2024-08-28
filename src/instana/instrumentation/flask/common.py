# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import wrapt
import flask
from importlib.metadata import version
from typing import Callable, Tuple, Dict, Any, TYPE_CHECKING, Union

from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.singletons import tracer, agent
from instana.propagators.format import Format
from instana.instrumentation.flask import signals_available


if TYPE_CHECKING:
    from instana.span.span import InstanaSpan
    from werkzeug.exceptions import HTTPException
    from flask.typing import ResponseReturnValue
    from jinja2.environment import Template

    if signals_available:
        from werkzeug.datastructures.headers import Headers
    else:
        from werkzeug.datastructures import Headers


@wrapt.patch_function_wrapper('flask', 'templating._render')
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


@wrapt.patch_function_wrapper('flask', 'Flask.handle_user_exception')
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
                    if hasattr(response, 'code'):
                        status_code = response.code
                    else:
                        status_code = response.status_code

                if 500 <= status_code:
                    span.record_exception(exc)

                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, int(status_code))

                if hasattr(response, 'headers'):
                    tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)
                    value = "intid;desc=%s" % span.context.trace_id
                    if hasattr(response.headers, 'add'):
                        response.headers.add('Server-Timing', value)
                    elif type(response.headers) is dict or hasattr(response.headers, "__dict__"):
                        response.headers['Server-Timing'] = value
            if span and span.is_recording():
                span.end()
            flask.g.span = None
    except:
        logger.debug("handle_user_exception_with_instana:", exc_info=True)

    return response


def extract_custom_headers(
    span: "InstanaSpan", headers: Union[Dict[str, Any], "Headers"], format: bool
) -> None:
    if agent.options.extra_http_headers is None:
        return
    try:
        for custom_header in agent.options.extra_http_headers:
            # Headers are available in this format: HTTP_X_CAPTURE_THIS
            flask_header = ('HTTP_' + custom_header.upper()).replace('-', '_') if format else custom_header
            if flask_header in headers:
                span.set_attribute(
                    "http.header.%s" % custom_header, headers[flask_header]
                )

    except Exception:
        logger.debug("extract_custom_headers: ", exc_info=True)
