import sys
import threading

from .log import logger
from .util import every, to_json, stan_dictionary


if sys.version_info.major == 2:
    import Queue as queue
else:
    import queue


class Collector(object):
    def __init__(self, agent):
        logger.debug("Loading collector")
        self.agent = agent
        self.span_queue = queue.Queue()
        self.shutdown = threading.Event()
        self.shutdown.clear()
        self.context = None
        self.snapshot_data = None
        self.snapshot_data_sent = False

    def start(self):
        if self.agent.can_send():
            t = threading.Thread(target=self.prepare_and_report_data, args=())
            t.setDaemon(True)
            t.start()
        else:
            logger.warn("Collector started but the agent tells us we can't send anything out.")

    def set_context(self, context):
        self.context = context

    def prepare_and_report_data(self):
        logger.debug("prepare_and_report_data")

        def work():
            logger.debug("prepare_and_report_data loop")
            if self.shutdown.is_set():
                logger.debug("Thread shutdown signal from agent is active: Shutting down span reporting thread")
                return False

            payload = stan_dictionary()

            if self.snapshot_data and self.snapshot_data_sent is False:
                payload["metrics"] = self.collect_snapshot()

            if not self.span_queue.empty():
                payload["spans"] = self.__queued_spans()

            if len(payload) > 0:
                logger.debug(to_json(payload))
                self.agent.report_data_payload(payload)

        every(5, work, "Instana Collector: prepare_and_report_data")

    def collect_snapshot(self):
        ss = stan_dictionary()
        ss["arn"] = self.context.invoked_function_arn
        ss["version"] = self.context.function_version
        # ss["revision"]
        # ss["code_sha_256"]
        # ss["description"]
        ss["runtime"] = "python"
        # ss["handler"]
        # ss["timeout"]
        ss["memory_size"] = self.context.memory_limit_in_mb
        # ss["last_modified"]
        # ss["aws_grouping_zone"]
        # ss["tags"]
        # ss["event_source_mappings"]
        # ss["legacy_endpoint_used"]
        return ss

    def __queued_spans(self):
        """ Get all of the spans in the queue """
        span = None
        spans = []
        while True:
            try:
                span = self.span_queue.get(False)
            except queue.Empty:
                break
            else:
                spans.append(span)
        return spans
