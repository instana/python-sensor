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
                self._collect_connection_tags(scope.span, event)
                self._collect_command_tags(scope.span, event)

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

        def _collect_connection_tags(self, span, event):
            (host, port) = event.connection_id

            span.set_tag("driver", "pymongo")
            span.set_tag("host", host)
            span.set_tag("port", str(port))
            span.set_tag("db", event.database_name)

        def _collect_command_tags(self, span, event):
            """
            Extract MongoDB command name and arguments and attach it to the span
            """
            cmd = event.command_name
            span.set_tag("command", cmd)
            
            if cmd == "find":
                span.set_tag("filter", event.command.get("filter"))
            elif cmd == "insert":
                span.set_tag("json", event.command.get("documents"))
            elif cmd == "update":
                span.set_tag("json", event.command.get("updates"))
            elif cmd == "delete":
                span.set_tag("json", event.command.get("deletes"))
            elif cmd == "aggregate":
                span.set_tag("json", event.command.get("pipeline"))
            elif cmd == "mapreduce":
                data = {
                    "map": event.command.get("map"),
                    "reduce": event.command.get("reduce")
                }
                if event.command.has_key("query"):
                    data["query"] = event.command.get("query")
                
                span.set_tag("json", data)

    monitoring.register(MongoCommandTracer())

    logger.debug("Instrumenting pymongo")

except ImportError:
    pass
