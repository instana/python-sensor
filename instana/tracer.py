from basictracer import BasicTracer
import instana.recorder as r
import opentracing
import instana.options as o
import instana.sensor as s


class InstanaTracer(BasicTracer):
    sensor = None

    def __init__(self, options=o.Options()):
        self.sensor = s.Sensor(options)
        super(InstanaTracer, self).__init__(
            r.InstanaRecorder(self.sensor), r.InstanaSampler())


def init(options):
    opentracing.tracer = InstanaTracer(options)
