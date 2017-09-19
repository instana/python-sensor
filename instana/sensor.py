import instana.options as o
import instana.log as l
import instana.meter as m
import instana.agent as a
import os


class Sensor(object):
    options = None
    meter = None
    service_name = None
    agent = None

    def __init__(self, options):
        self.set_options(options)
        l.init(options.log_level)
        self.configure_service_name()
        self.agent = a.Agent(self)
        self.meter = m.Meter(self)

        l.debug("initialized sensor")

    def set_options(self, options):
        self.options = options
        if not self.options:
            self.options = o.Options()

    def configure_service_name(self):
        if self.options:
            self.service_name = self.options.service

        if len(self.service_name) == 0:
            self.service_name = os.path.basename(__file__)

    def handle_fork(self):
        self.agent = a.Agent(self)
        self.meter = m.Meter(self)
