# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Host Collector: Manages the periodic collection of metrics & snapshot data
"""
from time import time
from ..log import logger
from .base import BaseCollector
from ..util import DictionaryOfStan
from .helpers.runtime import RuntimeHelper


class HostCollector(BaseCollector):
    """ Collector for AWS Fargate """
    def __init__(self, agent):
        super(HostCollector, self).__init__(agent)
        logger.debug("Loading Host Collector")

        # Indicates if this Collector has all requirements to run successfully
        self.ready_to_start = True

        # Populate the collection helpers
        self.helpers.append(RuntimeHelper(self))

    def start(self):
        if self.ready_to_start is False:
            logger.warning("Host Collector is missing requirements and cannot monitor this environment.")
            return

        super(HostCollector, self).start()

    def prepare_and_report_data(self):
        """
        We override this method from the base class so that we can handle the wait4init
        state machine case.
        """
        try:
            if self.agent.machine.fsm.current == "wait4init":
                # Test the host agent if we're ready to send data
                if self.agent.is_agent_ready():
                    if self.agent.machine.fsm.current != "good2go":
                        logger.debug("Agent is ready.  Getting to work.")
                        self.agent.machine.fsm.ready()
                else:
                    return

            if self.agent.machine.fsm.current == "good2go" and self.agent.is_timed_out():
                logger.info("The Instana host agent has gone offline or is no longer reachable for > 1 min.  Will retry periodically.")
                self.agent.reset()
        except Exception:
            logger.debug('Harmless state machine thread disagreement.  Will self-correct on next timer cycle.')

        super(HostCollector, self).prepare_and_report_data()

    def should_send_snapshot_data(self):
        delta = int(time()) - self.snapshot_data_last_sent
        if delta > self.snapshot_data_interval:
            return True
        return False

    def prepare_payload(self):
        payload = DictionaryOfStan()
        payload["spans"] = []
        payload["profiles"] = []
        payload["metrics"]["plugins"] = []

        try:
            if not self.span_queue.empty():
                payload["spans"] = self.queued_spans()

            if not self.profile_queue.empty():
                payload["profiles"] = self.queued_profiles()

            with_snapshot = self.should_send_snapshot_data()

            plugins = []
            for helper in self.helpers:
                plugins.extend(helper.collect_metrics(with_snapshot))

            payload["metrics"]["plugins"] = plugins

            if with_snapshot is True:
                self.snapshot_data_last_sent = int(time())
        except Exception:
            logger.debug("non-fatal prepare_payload:", exc_info=True)

        return payload
