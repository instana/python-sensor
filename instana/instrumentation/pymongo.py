from __future__ import absolute_import

from ..log import logger
from ..singletons import tracer

try:
    import pymongo
    from pymongo import monitoring

    class MongoCommandTracer(monitoring.CommandListener):
        def __init__(self):
            self.__active_commands = {}

        def started(self, event):
            parent_span = tracer.active_span

            # return early if we're not tracing
            if parent_span is None:
                return

            with tracer.start_active_span("mongo", child_of=parent_span) as scope:
                self._collect_tags(scope.span, event)

                scope.span.set_tag("db", event.database_name)
                scope.span.set_tag("command", event.command_name)

                # include collection name into the namespace if provided
                if event.command.has_key(event.command_name):
                    scope.span.set_tag("collection", event.command.get(event.command_name))

                self.__active_commands[event.request_id] = scope

        def succeeded(self, event):
            active_span = self.__active_commands.pop(event.request_id, None)

            # return early if we're not tracing
            if active_span is None:
                return

        def failed(self, event):
            active_span = self.__active_commands.pop(event.request_id, None)

            # return early if we're not tracing
            if active_span is None:
                return

            active_span.log_exception(event.failure)

        def _collect_tags(self, span, event):
            (host, port) = event.connection_id

            span.set_tag("driver", "pymongo")
            span.set_tag("host", host)
            span.set_tag("port", str(port))

    monitoring.register(MongoCommandTracer())

    logger.debug("Instrumenting pymongo")

except ImportError:
    pass
