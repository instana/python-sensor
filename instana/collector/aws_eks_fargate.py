# (c) Copyright IBM Corp. 2023

"""
Collector for EKS Pods on AWS Fargate: Manages the periodic collection of metrics & snapshot data
"""

from time import time
from instana.log import logger
from instana.collector.base import BaseCollector
from instana.util import DictionaryOfStan


class EKSFargateCollector(BaseCollector):
    """ Collector for EKS Pods on AWS Fargate """

    def __init__(self, agent):
        super(EKSFargateCollector, self).__init__(agent)
        logger.debug("Loading Collector for EKS Pods on AWS Fargate ")

        self.snapshot_data = DictionaryOfStan()
        self.snapshot_data_sent = False
        self.podname = agent.podname

    def should_send_snapshot_data(self):
        return int(time()) - self.snapshot_data_last_sent > self.snapshot_data_interval

    def collect_snapshot(self, event, context):
        self.context = context
        self.event = event

        try:
            plugin_data = dict()
            plugin_data["name"] = "com.instana.plugin.aws.eks"
            plugin_data["entityId"] = self.self.podname
            self.snapshot_data["plugins"] = [plugin_data]
        except Exception:
            logger.debug("collect_snapshot error", exc_info=True)
        return self.snapshot_data

    def prepare_payload(self):
        payload = DictionaryOfStan()
        payload["spans"] = []
        payload["metrics"]["plugins"] = []

        try:
            if not self.span_queue.empty():
                payload["spans"] = self.queued_spans()

            with_snapshot = self.should_send_snapshot_data()

            plugins = []
            for helper in self.helpers:
                plugins.extend(helper.collect_metrics(with_snapshot=with_snapshot))

            payload["metrics"]["plugins"] = plugins

            if with_snapshot:
                self.snapshot_data_last_sent = int(time())
        except Exception:
            logger.debug("collect_snapshot error", exc_info=True)

        return payload
