import os
import socket
import sys
import threading as t
import time

import opentracing.ext.tags as ext
from basictracer import Sampler, SpanRecorder

import instana

from .agent_const import AGENT_TRACES_URL
from .json_span import CustomData, Data, HttpData, JsonSpan, MySQLData, SDKData, SoapData

if sys.version_info.major is 2:
    import Queue as queue
else:
    import queue


class InstanaRecorder(SpanRecorder):
    sensor = None
    registered_spans = ("django", "memcache", "mysql", "rpc-client",
                        "rpc-server", "soap", "urllib3", "wsgi")
    http_spans = ("django", "wsgi", "urllib3", "soap")
    entry_kind = ["entry", "server", "consumer"]
    exit_kind = ["exit", "client", "producer"]
    queue = queue.Queue()

    def __init__(self, sensor):
        super(InstanaRecorder, self).__init__()
        self.sensor = sensor
        self.run()

    def run(self):
        """ Span a background thread to periodically report queued spans """
        self.timer = t.Thread(target=self.report_spans)
        self.timer.daemon = True
        self.timer.name = "Instana Span Reporting"
        self.timer.start()

    def report_spans(self):
        """ Periodically report the queued spans """
        while 1:
            if self.sensor.agent.can_send() and self.queue.qsize() > 0:
                url = self.sensor.agent.make_url(AGENT_TRACES_URL)
                self.sensor.agent.request(url, "POST", self.queued_spans())
            time.sleep(1)

    def queue_size(self):
        """ Return the size of the queue; how may spans are queued, """
        return self.queue.qsize()

    def queued_spans(self):
        """ Get all of the spans in the queue """
        spans = []
        while True:
            try:
                s = self.queue.get(False)
            except queue.Empty:
                break
            else:
                spans.append(s)
        return spans

    def clear_spans(self):
        """ Clear the queue of spans """
        self.queued_spans()

    def record_span(self, span):
        """
        Convert the passed BasicSpan into an JsonSpan and
        add it to the span queue
        """
        if self.sensor.agent.can_send() or "INSTANA_TEST" in os.environ:
            json_span = None

            if span.operation_name in self.registered_spans:
                json_span = self.build_registered_span(span)
            else:
                json_span = self.build_sdk_span(span)

            self.queue.put(json_span)

    def build_registered_span(self, span):
        """ Takes a BasicSpan and converts it into a registered JsonSpan """
        data = Data(baggage=span.context.baggage,
                    custom=CustomData(tags=span.tags,
                                      logs=self.collect_logs(span)))

        if span.operation_name in self.http_spans:
            data.http = HttpData(host=self.get_host_name(span),
                                 url=self.get_string_tag(span, ext.HTTP_URL),
                                 method=self.get_string_tag(span, ext.HTTP_METHOD),
                                 status=self.get_tag(span, ext.HTTP_STATUS_CODE),
                                 error=self.get_tag(span, 'http.error'))

        if span.operation_name == "soap":
            data.soap = SoapData(action=self.get_tag(span, 'soap.action'))

        if span.operation_name == "mysql":
            data.mysql = MySQLData(host=self.get_tag(span, 'host'),
                                   db=self.get_tag(span, ext.DATABASE_INSTANCE),
                                   user=self.get_tag(span, ext.DATABASE_USER),
                                   stmt=self.get_tag(span, ext.DATABASE_STATEMENT))
            if len(data.custom.logs.keys()):
                tskey = list(data.custom.logs.keys())[0]
                data.mysql.error = data.custom.logs[tskey]['message']

        entityFrom = {'e': self.sensor.agent.from_.pid,
                      'h': self.sensor.agent.from_.agentUuid}

        json_span = JsonSpan(n=span.operation_name,
                             t=span.context.trace_id,
                             p=span.parent_id,
                             s=span.context.span_id,
                             ts=int(round(span.start_time * 1000)),
                             d=int(round(span.duration * 1000)),
                             f=entityFrom,
                             data=data)

        error = self.get_tag(span, "error", False)
        ec = self.get_tag(span, "ec", None)

        if error and ec:
            json_span.error = error
            json_span.ec = ec

        return json_span

    def build_sdk_span(self, span):
        """ Takes a BasicSpan and converts into an SDK type JsonSpan """

        custom_data = CustomData(tags=span.tags,
                                 logs=self.collect_logs(span))

        sdk_data = SDKData(name=span.operation_name,
                           custom=custom_data)

        sdk_data.Type = self.get_span_kind(span)
        data = Data(service=self.get_service_name(span), sdk=sdk_data)
        entityFrom = {'e': self.sensor.agent.from_.pid,
                      'h': self.sensor.agent.from_.agentUuid}

        json_span = JsonSpan(
                             t=span.context.trace_id,
                             p=span.parent_id,
                             s=span.context.span_id,
                             ts=int(round(span.start_time * 1000)),
                             d=int(round(span.duration * 1000)),
                             n="sdk",
                             f=entityFrom,
                             data=data)

        error = self.get_tag(span, "error", False)
        ec = self.get_tag(span, "ec", None)

        if error and ec:
            json_span.error = error
            json_span.ec = ec

        return json_span

    def get_tag(self, span, tag, default=None):
        if tag in span.tags:
            return span.tags[tag]

        return default

    def get_string_tag(self, span, tag):
        ret = self.get_tag(span, tag)
        if not ret:
            return ""

        return ret

    def get_host_name(self, span):
        h = self.get_string_tag(span, "http.host")
        if len(h) > 0:
            return h

        h = socket.gethostname()
        if h and len(h) > 0:
            return h

        return "localhost"

    def get_service_name(self, span):
        return instana.service_name

    def get_span_kind(self, span):
        kind = ""
        if "span.kind" in span.tags:
            if span.tags["span.kind"] in self.entry_kind:
                kind = "entry"
            elif span.tags["span.kind"] in self.exit_kind:
                kind = "exit"
            else:
                kind = "local"
        return kind

    def collect_logs(self, span):
        logs = {}
        for l in span.logs:
            ts = int(round(l.timestamp * 1000))
            if ts not in logs:
                logs[ts] = {}

            for f in l.key_values:
                logs[ts][f] = l.key_values[f]

        return logs


class InstanaSampler(Sampler):

    def sampled(self, _):
        return False
