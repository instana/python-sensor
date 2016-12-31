from basictracer import Sampler, SpanRecorder
import instana.log as l
import instana.agent_const as a
import thread
import time

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
            data = self.get_span_log_field(span, "data")
            if not data.service:
                data.service = self.sensor.service_name
                
            thread.start_new_thread(self.sensor.agent.request,
                                    (self.sensor.agent.make_url(a.AGENT_TRACES_URL), "POST",
                                     [InstanaSpan(t=span.context.trace_id,
                                                 p=span.parent_id,
                                                 s=span.context.span_id,
                                                 ts=int(round(span.start_time * 1000)),
                                                 d=int(round(span.duration * 1000)),
                                                 n=self.get_string_span_log_field(span, "type"),
                                                 f=self.sensor.agent.from_,
                                                 data=data)]))

    def get_string_span_log_field(self, span, field):
        ret = self.get_span_log_field(span, field)
        if not ret:
            return ""

        return ret

    def get_span_log_field(self, span, field):
        for e in span.logs:
            if field in e.key_values:
                return e.key_values[field]

        return None

class InstanaSampler(Sampler):
    def sampled(self, trace_id):
        return False
