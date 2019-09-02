from __future__ import absolute_import

from .meter import Meter
from .options import Options


class Sensor(object):
    options = None
    agent = None
    meter = None

    def __init__(self, agent, options=None):
        self.set_options(options)
        self.agent = agent
        self.meter = Meter(agent)

    def set_options(self, options):
        if options is None:
            self.options = Options()
        else:
            self.options = options

    def start(self):
        # Nothing to do for the Sensor;  Pass onto Meter
        self.meter.start()

    def handle_fork(self):
        # Nothing to do for the Sensor;  Pass onto Meter
        self.meter.handle_fork()
