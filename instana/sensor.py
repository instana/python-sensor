from __future__ import absolute_import

from .log import init as init_logger
from .log import logger
from .meter import Meter
from .options import Options


class Sensor(object):
    options = None
    agent = None
    meter = None

    def __init__(self, agent, options=None):
        self.set_options(options)
        init_logger(self.options.log_level)

        self.agent = agent
        self.meter = Meter(agent)

    def set_options(self, options):
        self.options = options
        if not self.options:
            self.options = Options()

    def handle_fork(self):
        # Nothing to do for the Sensor;  Pass onto Meter
        self.meter.handle_fork()


global_sensor = None
