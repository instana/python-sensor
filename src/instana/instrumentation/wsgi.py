# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instana WSGI Middleware
"""

from typing import Any, Callable

from opentelemetry import context

from instana.util.wsgi_utils import (
    build_start_response,
    create_span_with_context,
    end_span_after_iterating,
)


class InstanaWSGIMiddleware(object):
    """Instana WSGI middleware"""

    def __init__(self, app: Callable, status_as_string: bool = True) -> None:
        self.app = app
        self.status_as_string = status_as_string

    def __call__(self, environ: dict[str, Any], start_response: Callable) -> object:
        try:
            span, token = create_span_with_context(environ)
            wrapped_start_response = build_start_response(
                span, start_response, status_as_string=self.status_as_string
            )
        except Exception:
            return self.app(environ, start_response)

        try:
            iterable = self.app(environ, wrapped_start_response)
            return end_span_after_iterating(iterable, span, token)
        except Exception as exc:
            if span and span.is_recording():
                span.record_exception(exc)
                span.end()
            if token:
                context.detach(token)
            raise exc
