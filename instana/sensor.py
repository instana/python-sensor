import instana.options as o
import instana.meter as m
import instana.agent as a
from instana import log


class Sensor(object):
    options = None
    meter = None
    service_name = None
    agent = None

    def __init__(self, options):
        self.set_options(options)
        log.init(options.log_level)
        self.configure_service_name()
        self.agent = a.Agent(self)
        self.meter = m.Meter(self)

        log.debug("initialized sensor")

    def set_options(self, options):
        self.options = options
        if not self.options:
            self.options = o.Options()

    def configure_service_name(self):
        if self.options:
            self.service_name = self.options.service

    def handle_fork(self):
        self.agent = a.Agent(self)
        self.meter = m.Meter(self)
