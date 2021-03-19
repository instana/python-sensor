# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

from __future__ import absolute_import

import re

from ..log import logger
from ..singletons import tracer

try:
    import sqlalchemy
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    url_regexp = re.compile(r"\/\/(\S+@)")


    @event.listens_for(Engine, 'before_cursor_execute', named=True)
    def receive_before_cursor_execute(**kw):
        try:
            parent_span = tracer.active_span

            # If we're not tracing, just return
            if parent_span is None:
                return

            scope = tracer.start_active_span("sqlalchemy", child_of=parent_span)
            context = kw['context']
            context._stan_scope = scope

            conn = kw['conn']
            url = str(conn.engine.url)
            scope.span.set_tag('sqlalchemy.sql', kw['statement'])
            scope.span.set_tag('sqlalchemy.eng', conn.engine.name)
            scope.span.set_tag('sqlalchemy.url', url_regexp.sub('//', url))
        except Exception as e:
            logger.debug(e)
        finally:
            return


    @event.listens_for(Engine, 'after_cursor_execute', named=True)
    def receive_after_cursor_execute(**kw):
        context = kw['context']

        if context is not None and hasattr(context, '_stan_scope'):
            scope = context._stan_scope
            if scope is not None:
                scope.close()


    error_event = "handle_error"
    # Handle dbapi_error event; deprecated since version 0.9
    if sqlalchemy.__version__[0] == "0":
        error_event = "dbapi_error"


    @event.listens_for(Engine, error_event, named=True)
    def receive_handle_db_error(**kw):
        context = kw['exception_context'].execution_context

        if context is not None and hasattr(context, '_stan_scope'):
            scope = context._stan_scope
            if scope is not None:
                scope.span.mark_as_errored()

                if context.exception:
                    e = context.exception
                    scope.span.set_tag('sqlalchemy.err', str(e))
                else:
                    scope.span.set_tag('sqlalchemy.err', "No %s specified." % error_event)
                scope.close()


    logger.debug("Instrumenting sqlalchemy")
except ImportError:
    pass
