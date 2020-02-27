from __future__ import absolute_import

import os
import sys
import threading

from .log import logger
from .util import every
import instana.singletons

from basictracer import Sampler

from .json_span import (AWSLambdaData, CassandraData, CouchbaseData, CustomData, Data, HttpData, JsonSpan, LogData,
                        MongoDBData, MySQLData, PostgresData, RabbitmqData, RedisData, RenderData,
                        RPCData, SDKData, SoapData, SQLAlchemyData)

if sys.version_info.major == 2:
    import Queue as queue
else:
    import queue


class InstanaRecorder(object):
    THREAD_NAME = "Instana Span Reporting"
    registered_spans = ("aiohttp-client", "aiohttp-server", "aws.lambda.entry", "cassandra", "couchbase",
                        "django", "log","memcache", "mongo", "mysql", "postgres", "rabbitmq", "redis", "render",
                        "rpc-client", "rpc-server", "sqlalchemy", "soap", "tornado-client", "tornado-server",
                        "urllib3", "wsgi")

    http_spans = ("aiohttp-client", "aiohttp-server", "django", "http", "soap", "tornado-client",
                  "tornado-server", "urllib3", "wsgi")

    exit_spans = ("aiohttp-client", "cassandra", "couchbase", "log", "memcache", "mongo", "mysql", "postgres",
                  "rabbitmq", "redis", "rpc-client", "sqlalchemy", "soap", "tornado-client", "urllib3",
                  "pymongo")

    entry_spans = ("aiohttp-server", "aws.lambda.entry", "django", "wsgi", "rabbitmq", "rpc-server", "tornado-server")

    local_spans = ("render")

    entry_kind = ["entry", "server", "consumer"]
    exit_kind = ["exit", "client", "producer"]

    # Recorder thread for collection/reporting of spans
    thread = None

    def __init__(self):
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

            # logger.debug("Recorded span: %s", json_span)

            self.queue.put(json_span)

    def build_registered_span(self, span):
        """ Takes a BasicSpan and converts it into a registered JsonSpan """
        data = Data()

        kind = 1
        if span.operation_name in self.entry_spans:
            # entry
            self._populate_entry_span_data(span, data)
        elif span.operation_name in self.exit_spans:
            kind = 2 # exit
            self._populate_exit_span_data(span, data)
        elif span.operation_name in self.local_spans:
            kind = 3 # intermediate span
            self._populate_local_span_data(span, data)

        if data.rabbitmq and data.rabbitmq.sort == 'consume':
            kind = 1  # entry

        return JsonSpan(span, kind, data, instana.singletons.agent)

    def _populate_entry_span_data(self, span, data):
        if span.operation_name in self.http_spans:
            data.http = HttpData(span)
            if span.operation_name == "soap":
                data.soap = SoapData(span)
        elif span.operation_name == "aws.lambda.entry":
            data.aws_lambda = AWSLambdaData(span)
        elif span.operation_name == "rabbitmq":
            data.rabbitmq = RabbitmqData(span)
        elif span.operation_name == "rpc-server":
            data.rpc = RPCData(span)
        else:
            logger.debug("SpanRecorder: Unknown entry span: %s" % span.operation_name)

    def _populate_local_span_data(self, span, data):
        if span.operation_name == "render":
            data.render = RenderData(span)
            data.log = LogData(span)
        else:
            logger.debug("SpanRecorder: Unknown local span: %s" % span.operation_name)

    def _populate_exit_span_data(self, span, data):
        if span.operation_name in self.http_spans:
            data.http = HttpData(span)
            if span.operation_name == "soap":
                data.soap = SoapData(span)

        elif span.operation_name == "rabbitmq":
            data.rabbitmq = RabbitmqData(span)

        elif span.operation_name == "cassandra":
            data.cassandra = CassandraData(span)

        elif span.operation_name == "couchbase":
            data.couchbase = CouchbaseData(span)

        elif span.operation_name == "redis":
            data.redis = RedisData(span)

        elif span.operation_name == "rpc-client":
            data.rpc = RPCData(span)

        elif span.operation_name == "sqlalchemy":
            data.sqlalchemy = SQLAlchemyData(span)

        elif span.operation_name == "mysql":
            data.mysql = MySQLData(span)
            if (data.custom is not None) and (data.custom.logs is not None) and len(data.custom.logs):
                tskey = list(data.custom.logs.keys())[0]
                data.mysql.error = data.custom.logs[tskey]['message']

        elif span.operation_name == "postgres":
            data.pg = PostgresData(span)
            if (data.custom is not None) and (data.custom.logs is not None) and len(data.custom.logs):
                tskey = list(data.custom.logs.keys())[0]
                data.pg.error = data.custom.logs[tskey]['message']

        elif span.operation_name == "mongo":
            data.mongo = MongoDBData(span)

        elif span.operation_name == "log":
            data.log = {}
            # use last special key values
            # TODO - logic might need a tweak here
            for l in span.logs:
                if "message" in l.key_values:
                    data.log["message"] = l.key_values.pop("message", None)
                if "parameters" in l.key_values:
                    data.log["parameters"] = l.key_values.pop("parameters", None)
        else:
            logger.debug("SpanRecorder: Unknown exit span: %s" % span.operation_name)

    def build_sdk_span(self, span):
        """ Takes a BasicSpan and converts into an SDK type JsonSpan """

        custom_data = CustomData(tags=span.tags,
                                 logs=span.collect_logs())

        sdk_data = SDKData(name=span.operation_name,
                           custom=custom_data,
                           Type=self.get_span_kind_as_string(span))

        if "arguments" in span.tags:
            sdk_data.arguments = span.tags["arguments"]

        if "return" in span.tags:
            sdk_data.Return = span.tags["return"]

        data = Data(service=instana.singletons.agent.options.service_name, sdk=sdk_data)
        return JsonSpan(span, self.get_span_kind_as_int(span), data, instana.singletons.agent)

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


class AWSLambdaRecorder(InstanaRecorder):
    def __init__(self, agent):
        self.agent = agent
        super(AWSLambdaRecorder, self).__init__()

    def record_span(self, span):
        """
        Convert the passed BasicSpan into an JsonSpan and
        add it to the span queue
        """
        json_span = None

        if span.operation_name in self.registered_spans:
            json_span = self.build_registered_span(span)
        else:
            json_span = self.build_sdk_span(span)

        logger.debug("Recorded span: %s", json_span)
        self.agent.collector.span_queue.put(json_span)


class InstanaSampler(Sampler):
    def sampled(self, _):
        return False
