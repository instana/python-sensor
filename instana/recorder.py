from basictracer import Sampler, SpanRecorder
import instana.agent_const as a
import instana.http as http
import instana.custom as c
import threading as t
import opentracing.ext.tags as ext
import socket
import instana.data as d

class InstanaSpan(object):
    t = 0
    p = None
    s = 0
    ts = 0
    d = 0
    n = None
    f = None
    data = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class InstanaRecorder(SpanRecorder):
    sensor = None

    def __init__(self, sensor):
        super(InstanaRecorder, self).__init__()
        self.sensor = sensor

    def record_span(self, span):
        if self.sensor.agent.can_send():
            data = d.Data(service=self.get_service_name(span),
                          http=http.HttpData(host=self.get_host_name(span),
                                             url=self.get_string_tag(span, ext.HTTP_URL),
                                             method=self.get_string_tag(span, ext.HTTP_METHOD),
                                             status=self.get_tag(span, ext.HTTP_STATUS_CODE)),
                          custom=c.CustomData(tags=span.tags,
                                              logs=self.collect_logs(span)))

            t.Thread(target=self.sensor.agent.request,
                     args=(self.sensor.agent.make_url(a.AGENT_TRACES_URL), "POST",
                           [InstanaSpan(t=span.context.trace_id,
                                        p=span.parent_id,
                                        s=span.context.span_id,
                                        ts=int(round(span.start_time * 1000)),
                                        d=int(round(span.duration * 1000)),
                                        n=self.get_http_type(span),
                                        f=self.sensor.agent.from_,
                                        data=data)])).start()

    def get_tag(self, span, tag):
        if tag in span.tags:
            return span.tags[tag]

        return None

    def get_string_tag(self, span, tag):
        ret = self.get_tag(span, tag)
        if not ret:
            return ""

        return ret

    def get_host_name(self, span):
        h = self.get_string_tag(span, ext.PEER_HOSTNAME)
        if len(h) > 0:
            return h

        h = socket.gethostname()
        if h and len(h) > 0:
            return h

        return "localhost"

    def get_service_name(self, span):
        s = self.get_string_tag(span, ext.COMPONENT)
        if len(s) > 0:
            return s

        s = self.get_string_tag(span, ext.PEER_SERVICE)
        if len(s) > 0:
            return s

        return self.sensor.service_name

    def get_http_type(self, span):
        k = self.get_string_tag(span, ext.SPAN_KIND)
        if k == ext.SPAN_KIND_RPC_CLIENT:
            return http.HTTP_CLIENT

        return http.HTTP_SERVER

    def collect_logs(self, span):
        logs = {}
        for l in span.logs:
            ts = int(round(l.timestamp * 1000))
            if not ts in logs:
                logs[ts] = {}

            for f in l.key_values:
                logs[ts][f] = l.key_values[f]

        return logs

class InstanaSampler(Sampler):

    def sampled(self, _):
        return False
