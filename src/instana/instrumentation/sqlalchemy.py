# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018


import re
from typing import Any, Dict

from opentelemetry import context, trace

from instana.log import logger
from instana.span.span import InstanaSpan, get_current_span
from instana.span_context import SpanContext
from instana.util.traceutils import get_tracer_tuple, tracing_is_off

try:
    from sqlalchemy import __version__ as sqlalchemy_version
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    url_regexp = re.compile(r"\/\/(\S+@)")

    @event.listens_for(Engine, "before_cursor_execute", named=True)
    def receive_before_cursor_execute(
        **kw: Dict[str, Any],
    ) -> None:
        try:
            # If we're not tracing, just return
            if tracing_is_off():
                return

            tracer, parent_span, _ = get_tracer_tuple()
            parent_context = parent_span.get_span_context() if parent_span else None

            span = tracer.start_span("sqlalchemy", span_context=parent_context)
            conn = kw["conn"]
            conn.span = span
            span.set_attribute("sqlalchemy.sql", kw["statement"])
            span.set_attribute("sqlalchemy.eng", conn.engine.name)
            span.set_attribute(
                "sqlalchemy.url", url_regexp.sub("//", str(conn.engine.url))
            )

            ctx = trace.set_span_in_context(span)
            token = context.attach(ctx)
            conn.token = token
        except Exception:
            logger.debug(
                "Instrumenting sqlalchemy @ receive_before_cursor_execute",
                exc_info=True,
            )

    @event.listens_for(Engine, "after_cursor_execute", named=True)
    def receive_after_cursor_execute(
        **kw: Dict[str, Any],
    ) -> None:
        try:
            # If we're not tracing, just return
            if tracing_is_off():
                return

            current_span = get_current_span()
            conn = kw["conn"]
            if current_span.is_recording():
                current_span.end()
            if hasattr(conn, "token"):
                context.detach(conn.token)
                conn.token = None
        except Exception:
            logger.debug(
                "Instrumenting sqlalchemy @ receive_after_cursor_execute",
                exc_info=True,
            )

    error_event = "handle_error"
    # Handle dbapi_error event; deprecated since version 0.9
    if sqlalchemy_version[0] == "0":
        error_event = "dbapi_error"

    def _set_error_attributes(
        context: SpanContext,
        exception_string: str,
        span: InstanaSpan,
    ) -> None:
        context_exception = None, None
        if hasattr(context, exception_string):
            context_exception = getattr(context, exception_string)
        if span and context_exception:
            span.record_exception(context_exception)
        else:
            span.record_exception(f"No {error_event} specified.")
        if span.is_recording():
            span.end()

    @event.listens_for(Engine, error_event, named=True)
    def receive_handle_db_error(
        **kw: Dict[str, Any],
    ) -> None:
        try:
            if tracing_is_off():
                return

            current_span = get_current_span()

            # support older db error event
            if error_event == "dbapi_error":
                context = kw.get("context")
                exception_string = "exception"
            else:
                context = kw.get("exception_context")
                exception_string = "sqlalchemy_exception"

            if context:
                _set_error_attributes(context, exception_string, current_span)
        except Exception:
            logger.debug(
                "Instrumenting sqlalchemy @ receive_handle_db_error",
                exc_info=True,
            )

    logger.debug("Instrumenting sqlalchemy")

except ImportError:
    pass
