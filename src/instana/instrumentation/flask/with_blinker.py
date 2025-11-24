# (c) Copyright IBM Corp. 2021, 2025
# (c) Copyright Instana Inc. 2019


from typing import Any, Callable, Dict, Tuple

import flask
import wrapt
from flask import got_request_exception, request_finished, request_started
from opentelemetry.semconv.trace import SpanAttributes

from instana.instrumentation.flask.common import (
    create_span,
    inject_span,
    teardown_request_with_instana,
)
from instana.log import logger


def request_started_with_instana(sender: flask.app.Flask, **extra: Any) -> None:
    try:
        create_span()
    except Exception:
        logger.debug("Flask request_started_with_instana", exc_info=True)


def request_finished_with_instana(
    sender: flask.app.Flask, response: flask.wrappers.Response, **extra: Any
) -> None:
    inject_span(response, "Flask request_finished_with_instana")


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
