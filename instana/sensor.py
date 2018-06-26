from __future__ import absolute_import

import instana.log as log

from .agent import Agent
from .meter import Meter
from .options import Options


class Sensor(object):
    options = None
    meter = None
    agent = None

    def __init__(self, options):
        self.set_options(options)
        log.init(options.log_level)
        self.agent = Agent(self)
        self.meter = Meter(self)

        log.debug("initialized sensor")

    def set_options(self, options):
        self.options = options
        if not self.options:
            self.options = Options()

    def handle_fork(self):
        self.agent = Agent(self)
        self.meter = Meter(self)
