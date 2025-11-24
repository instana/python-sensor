# (c) Copyright IBM Corp. 2021, 2025
# (c) Copyright Instana Inc. 2019


from typing import Callable, Dict, Tuple

import flask
import wrapt

from instana.instrumentation.flask.common import (
    create_span,
    inject_span,
    teardown_request_with_instana,
)
from instana.log import logger


def before_request_with_instana() -> None:
    try:
        create_span()
    except Exception:
        logger.debug("Flask before_request", exc_info=True)

    return None


def after_request_with_instana(
    response: flask.wrappers.Response,
) -> flask.wrappers.Response:
    inject_span(response, "Flask after_request", set_flask_g_none=True)
    return response


@wrapt.patch_function_wrapper("flask", "Flask.full_dispatch_request")
def full_dispatch_request_with_instana(
    wrapped: Callable[..., flask.wrappers.Response],
    instance: flask.app.Flask,
    argv: Tuple,
    kwargs: Dict,
) -> flask.wrappers.Response:
    if not hasattr(instance, "_stan_wuz_here"):
        logger.debug(
            "Flask(vanilla): Applying flask before/after instrumentation funcs"
        )
        setattr(instance, "_stan_wuz_here", True)
        instance.before_request(before_request_with_instana)
        instance.after_request(after_request_with_instana)
        instance.teardown_request(teardown_request_with_instana)
    return wrapped(*argv, **kwargs)


logger.debug("Instrumenting flask (without blinker support)")
