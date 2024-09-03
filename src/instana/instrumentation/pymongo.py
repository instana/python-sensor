# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


from instana.span.span import InstanaSpan
from instana.log import logger
from instana.util.traceutils import get_tracer_tuple, tracing_is_off

try:
    import pymongo
    from bson import json_util
    from opentelemetry.semconv.trace import SpanAttributes

    class MongoCommandTracer(pymongo.monitoring.CommandListener):
        def __init__(self) -> None:
            self.__active_commands = {}

        def started(self, event: pymongo.monitoring.CommandStartedEvent) -> None:
            tracer, parent_span, _ = get_tracer_tuple()
            # return early if we're not tracing
            if tracing_is_off():
                return
            parent_context = parent_span.get_span_context() if parent_span else None

            with tracer.start_as_current_span(
                "mongo", span_context=parent_context
            ) as span:
                self._collect_connection_tags(span, event)
                self._collect_command_tags(span, event)

                # include collection name into the namespace if provided
                if event.command_name in event.command:
                    span.set_attribute(
                        SpanAttributes.DB_MONGODB_COLLECTION,
                        event.command.get(event.command_name),
                    )

                self.__active_commands[event.request_id] = span

        def succeeded(self, event: pymongo.monitoring.CommandStartedEvent) -> None:
            active_span = self.__active_commands.pop(event.request_id, None)

            # return early if we're not tracing
            if active_span is None:
                return

        def failed(self, event: pymongo.monitoring.CommandStartedEvent) -> None:
            active_span = self.__active_commands.pop(event.request_id, None)

            # return early if we're not tracing
            if active_span is None:
                return

            active_span.log_exception(event.failure)

        def _collect_connection_tags(
            self, span: InstanaSpan, event: pymongo.monitoring.CommandStartedEvent
        ) -> None:
            (host, port) = event.connection_id

            span.set_attribute(SpanAttributes.SERVER_ADDRESS, host)
            span.set_attribute(SpanAttributes.SERVER_PORT, str(port))
            span.set_attribute(SpanAttributes.DB_NAME, event.database_name)

        def _collect_command_tags(self, span, event) -> None:
            """
            Extract MongoDB command name and arguments and attach it to the span
            """
            cmd = event.command_name
            span.set_attribute("command", cmd)

            for key in ["filter", "query"]:
                if key in event.command:
                    span.set_attribute(
                        "filter", json_util.dumps(event.command.get(key))
                    )
                    break

            # The location of command documents within the command object depends on the name
            # of this command. This is the name -> command object key mapping
            cmd_doc_locations = {
                "insert": "documents",
                "update": "updates",
                "delete": "deletes",
                "aggregate": "pipeline",
            }

            cmd_doc = None
            if cmd in cmd_doc_locations:
                cmd_doc = event.command.get(cmd_doc_locations[cmd])
            elif (
                cmd.lower() == "mapreduce"
            ):  # mapreduce command was renamed to mapReduce in pymongo 3.9.0
                # mapreduce command consists of two mandatory parts: map and reduce
                cmd_doc = {
                    "map": event.command.get("map"),
                    "reduce": event.command.get("reduce"),
                }

            if cmd_doc is not None:
                span.set_attribute("json", json_util.dumps(cmd_doc))

    pymongo.monitoring.register(MongoCommandTracer())

    logger.debug("Instrumenting pymongo")

except ImportError:
    pass
