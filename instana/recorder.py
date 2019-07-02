from __future__ import absolute_import

import os
import sys
import threading

import opentracing.ext.tags as ext
from basictracer import Sampler, SpanRecorder

import instana.singletons

from .json_span import (CustomData, Data, HttpData, JsonSpan, LogData, MySQLData, PostgresData,
                        RabbitmqData, RedisData, RenderData, RPCData, SDKData, SoapData,
                        SQLAlchemyData)
from .log import logger
from .util import every

if sys.version_info.major == 2:
    import Queue as queue
else:
    import queue


class InstanaRecorder(SpanRecorder):
    THREAD_NAME = "Instana Span Reporting"
    registered_spans = ("aiohttp-client", "aiohttp-server", "django", "log", "memcache", "mysql",
                        "postgres", "rabbitmq", "redis", "render", "rpc-client", "rpc-server", "sqlalchemy", "soap",
                        "tornado-client", "tornado-server", "urllib3", "wsgi")
    http_spans = ("aiohttp-client", "aiohttp-server", "django", "http", "soap", "tornado-client",
                  "tornado-server", "urllib3", "wsgi")

    exit_spans = ("aiohttp-client", "log", "memcache", "mysql", "postgres", "rabbitmq", "redis", "rpc-client",
                  "sqlalchemy", "soap", "tornado-client", "urllib3")
    entry_spans = ("aiohttp-server", "django", "wsgi", "rabbitmq", "rpc-server", "tornado-server")
    local_spans = ("log", "render")

    entry_kind = ["entry", "server", "consumer"]
    exit_kind = ["exit", "client", "producer"]

    # Recorder thread for collection/reporting of spans
    thread = None

    def __init__(self):
        super(InstanaRecorder, self).__init__()
        self.queue = queue.Queue()

    def start(self):
        """
        This function can be called at first boot or after a fork.  In either case, it will
        assure that the Recorder is in a proper state (via reset()) and spawn a new background
        thread to periodically report queued spans

        Note that this will abandon any previous thread object that (in the case of an `os.fork()`)
        should no longer exist in the forked process.

        (Forked processes carry forward only the thread that called `os.fork()`
        into the new process space.  All other background threads need to be recreated.)

        Calling this directly more than once without an actual fork will cause errors.
        """
        self.reset()
        self.thread.start()

    def reset(self):
        # Prepare the thread for span collection/reporting
        self.thread = threading.Thread(target=self.report_spans)
        self.thread.daemon = True
        self.thread.name = self.THREAD_NAME

    def handle_fork(self):
        self.start()

    def report_spans(self):
        """ Periodically report the queued spans """
        logger.debug(" -> Span reporting thread is now alive")

        def span_work():
            if instana.singletons.agent.should_threads_shutdown.is_set():
                logger.debug("Thread shutdown signal from agent is active: Shutting down span reporting thread")
                return False

            queue_size = self.queue.qsize()
            if queue_size > 0 and instana.singletons.agent.can_send():
                response = instana.singletons.agent.report_traces(self.queued_spans())
                if response:
                    logger.debug("reported %d spans", queue_size)
            return True

        every(2, span_work, "Span Reporting")

    def queue_size(self):
        """ Return the size of the queue; how may spans are queued, """
        return self.queue.qsize()

    def queued_spans(self):
        """ Get all of the spans in the queue """
        span = None
        spans = []
        while True:
            try:
                span = self.queue.get(False)
            except queue.Empty:
                break
            else:
                spans.append(span)
        return spans

    def clear_spans(self):
        """ Clear the queue of spans """
        self.queued_spans()

    def record_span(self, span):
        """
        Convert the passed BasicSpan into an JsonSpan and
        add it to the span queue
        """
        if instana.singletons.agent.can_send() or "INSTANA_TEST" in os.environ:
            json_span = None

            if span.operation_name in self.registered_spans:
                json_span = self.build_registered_span(span)
            else:
                json_span = self.build_sdk_span(span)

            self.queue.put(json_span)

    def build_registered_span(self, span):
        """ Takes a BasicSpan and converts it into a registered JsonSpan """
        data = Data()
        if len(span.context.baggage) > 0:
            data.baggage = span.context.baggage

        kind = 1 # entry
        if span.operation_name in self.exit_spans:
            kind = 2 # exit
        if span.operation_name in self.local_spans:
            kind = 3 # intermediate span

        logs = self.collect_logs(span)
        if len(logs) > 0:
            if data.custom is None:
                data.custom = CustomData()
            data.custom.logs = logs

        if span.operation_name in self.http_spans:
            data.http = HttpData(host=span.tags.pop("http.host", None),
                                 url=span.tags.pop(ext.HTTP_URL, None),
                                 path=span.tags.pop("http.path", None),
                                 params=span.tags.pop('http.params', None),
                                 method=span.tags.pop(ext.HTTP_METHOD, None),
                                 status=span.tags.pop(ext.HTTP_STATUS_CODE, None),
                                 path_tpl=span.tags.pop("http.path_tpl", None),
                                 error=span.tags.pop('http.error', None))

        if span.operation_name == "rabbitmq":
            data.rabbitmq = RabbitmqData(exchange=span.tags.pop('exchange', None),
                                         queue=span.tags.pop('queue', None),
                                         sort=span.tags.pop('sort', None),
                                         address=span.tags.pop('address', None),
                                         key=span.tags.pop('key', None))
            if data.rabbitmq.sort == 'consume':
                kind = 1 # entry

        if span.operation_name == "redis":
            data.redis = RedisData(connection=span.tags.pop('connection', None),
                                   driver=span.tags.pop('driver', None),
                                   command=span.tags.pop('command', None),
                                   error=span.tags.pop('redis.error', None),
                                   subCommands=span.tags.pop('subCommands', None))

        if span.operation_name == "rpc-client" or span.operation_name == "rpc-server":
            data.rpc = RPCData(flavor=span.tags.pop('rpc.flavor', None),
                               host=span.tags.pop('rpc.host', None),
                               port=span.tags.pop('rpc.port', None),
                               call=span.tags.pop('rpc.call', None),
                               call_type=span.tags.pop('rpc.call_type', None),
                               params=span.tags.pop('rpc.params', None),
                               baggage=span.tags.pop('rpc.baggage', None),
                               error=span.tags.pop('rpc.error', None))

        if span.operation_name == "render":
            data.render = RenderData(name=span.tags.pop('name', None),
                                     type=span.tags.pop('type', None))
            data.log = LogData(message=span.tags.pop('message', None),
                               parameters=span.tags.pop('parameters', None))

        if span.operation_name == "sqlalchemy":
            data.sqlalchemy = SQLAlchemyData(sql=span.tags.pop('sqlalchemy.sql', None),
                                             eng=span.tags.pop('sqlalchemy.eng', None),
                                             url=span.tags.pop('sqlalchemy.url', None),
                                             err=span.tags.pop('sqlalchemy.err', None))

        if span.operation_name == "soap":
            data.soap = SoapData(action=span.tags.pop('soap.action', None))

        if span.operation_name == "mysql":
            data.mysql = MySQLData(host=span.tags.pop('host', None),
                                   db=span.tags.pop(ext.DATABASE_INSTANCE, None),
                                   user=span.tags.pop(ext.DATABASE_USER, None),
                                   stmt=span.tags.pop(ext.DATABASE_STATEMENT, None))
            if (data.custom is not None) and (data.custom.logs is not None) and len(data.custom.logs):
                tskey = list(data.custom.logs.keys())[0]
                data.mysql.error = data.custom.logs[tskey]['message']

        if span.operation_name == "postgres":
            data.pg = PostgresData(host=span.tags.pop('host', None),
                                   db=span.tags.pop(ext.DATABASE_INSTANCE, None),
                                   user=span.tags.pop(ext.DATABASE_USER, None),
                                   stmt=span.tags.pop(ext.DATABASE_STATEMENT, None),
                                   error=span.tags.pop('pg.error', None))
            if (data.custom is not None) and (data.custom.logs is not None) and len(data.custom.logs):
                tskey = list(data.custom.logs.keys())[0]
                data.pg.error = data.custom.logs[tskey]['message']

        if span.operation_name == "log":
            data.log = {}
            # use last special key values
            # TODO - logic might need a tweak here
            for l in span.logs:
                if "message" in l.key_values:
                    data.log["message"] = l.key_values.pop("message", None)
                if "parameters" in l.key_values:
                    data.log["parameters"] = l.key_values.pop("parameters", None)

        entity_from = {'e': instana.singletons.agent.from_.pid,
                       'h': instana.singletons.agent.from_.agentUuid}

        json_span = JsonSpan(n=span.operation_name,
                             k=kind,
                             t=span.context.trace_id,
                             p=span.parent_id,
                             s=span.context.span_id,
                             ts=int(round(span.start_time * 1000)),
                             d=int(round(span.duration * 1000)),
                             f=entity_from,
                             data=data)

        if span.stack:
            json_span.stack = span.stack

        error = span.tags.pop("error", False)
        ec = span.tags.pop("ec", None)

        if error and ec:
            json_span.error = error
            json_span.ec = ec

        if len(span.tags) > 0:
            if data.custom is None:
                data.custom = CustomData()
            data.custom.tags = span.tags

        return json_span

    def build_sdk_span(self, span):
        """ Takes a BasicSpan and converts into an SDK type JsonSpan """

        custom_data = CustomData(tags=span.tags,
                                 logs=self.collect_logs(span))

        sdk_data = SDKData(name=span.operation_name,
                           custom=custom_data,
                           Type=self.get_span_kind_as_string(span))

        if "arguments" in span.tags:
            sdk_data.arguments = span.tags["arguments"]

        if "return" in span.tags:
            sdk_data.Return = span.tags["return"]

        data = Data(service=instana.singletons.agent.sensor.options.service_name, sdk=sdk_data)
        entity_from = {'e': instana.singletons.agent.from_.pid,
                       'h': instana.singletons.agent.from_.agentUuid}

        json_span = JsonSpan(t=span.context.trace_id,
                             p=span.parent_id,
                             s=span.context.span_id,
                             ts=int(round(span.start_time * 1000)),
                             d=int(round(span.duration * 1000)),
                             k=self.get_span_kind_as_int(span),
                             n="sdk",
                             f=entity_from,
                             data=data)

        error = span.tags.pop("error", False)
        ec = span.tags.pop("ec", None)

        if error and ec:
            json_span.error = error
            json_span.ec = ec

        return json_span

    def get_span_kind_as_string(self, span):
        """
            Will retrieve the `span.kind` tag and return the appropriate string value for the Instana backend or
            None if the tag is set to something we don't recognize.

        :param span: The span to search for the `span.kind` tag
        :return: String
        """
        kind = None
        if "span.kind" in span.tags:
            if span.tags["span.kind"] in self.entry_kind:
                kind = "entry"
            elif span.tags["span.kind"] in self.exit_kind:
                kind = "exit"
            else:
                kind = "intermediate"
        return kind

    def get_span_kind_as_int(self, span):
        """
            Will retrieve the `span.kind` tag and return the appropriate integer value for the Instana backend or
            None if the tag is set to something we don't recognize.

        :param span: The span to search for the `span.kind` tag
        :return: Integer
        """
        kind = None
        if "span.kind" in span.tags:
            if span.tags["span.kind"] in self.entry_kind:
                kind = 1
            elif span.tags["span.kind"] in self.exit_kind:
                kind = 2
            else:
                kind = 3
        return kind

    def collect_logs(self, span):
        """
            Collect up log data and feed it to the Instana brain.

        :param span: The span to search for logs in
        :return: Logs ready for consumption by the Instana brain.
        """
        logs = {}
        for log in span.logs:
            ts = int(round(log.timestamp * 1000))
            if ts not in logs:
                logs[ts] = {}

            if 'message' in log.key_values:
                logs[ts]['message'] = log.key_values['message']
            if 'event' in log.key_values:
                logs[ts]['event'] = log.key_values['event']
            if 'parameters' in log.key_values:
                logs[ts]['parameters'] = log.key_values['parameters']

        return logs


class InstanaSampler(Sampler):

    def sampled(self, _):
        return False
