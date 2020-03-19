from __future__ import absolute_import

from .meter import Meter


class Sensor(object):
    agent = None
    meter = None

    def __init__(self, agent):
        self.agent = agent
        self.meter = Meter(agent)

    def start(self):
        # Nothing to do for the Sensor;  Pass onto Meter
        self.meter.start()

    def handle_fork(self):
        # Nothing to do for the Sensor;  Pass onto Meter
        self.meter.handle_fork()
