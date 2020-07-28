from ...log import logger


class BaseHelper:
    def __init__(self, collector):
        self.collector = collector

    def collect_metrics(self, with_sendsnapshot = False):
        logger.debug("BaseHelper.collect_metrics must be overridden")