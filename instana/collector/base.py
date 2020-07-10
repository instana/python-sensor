import os
import sys
import threading

from ..log import logger
from ..util import every, DictionaryOfStan


if sys.version_info.major == 2:
    import Queue as queue
else:
    import queue


class BaseCollector(object):
    def __init__(self, agent):
        self.agent = agent
        self.span_queue = queue.Queue()
        self.thread_shutdown = threading.Event()
        self.thread_shutdown.clear()
        self.context = None
        self.event = None
        self.snapshot_data = None
        self.snapshot_data_sent = False
        self.lock = threading.Lock()

    def start(self):
        if self.agent.can_send():
            t = threading.Thread(target=self.thread_loop, args=())
            t.setDaemon(True)
            t.start()
        else:
            logger.warning("Collector started but the agent tells us we can't send anything out.")

    def shutdown(self):
        logger.debug("Collector.shutdown: Reporting final data.")
        self.thread_shutdown.set()
        self.prepare_and_report_data()

    def thread_loop(self):
        every(5, self.background_report, "Instana Collector: prepare_and_report_data")

    def background_report(self):
        if self.thread_shutdown.is_set():
            logger.debug("Thread shutdown signal is active: Shutting down reporting thread")
            return False
        return self.prepare_and_report_data()

    def prepare_payload(self):
        logger.debug("BaseCollector: prepare_payload needs to be overridden")

    def prepare_and_report_data(self):
        if "INSTANA_TEST" in os.environ:
            return True

        lock_acquired = self.lock.acquire(False)
        if lock_acquired:
            payload = self.prepare_payload()

            if len(payload) > 0:
                self.agent.report_data_payload(payload)
            else:
                logger.debug("prepare_and_report_data: No data to report")
            self.lock.release()
        else:
            logger.debug("prepare_and_report_data: Couldn't acquire lock")
        return True

    def collect_snapshot(self, *argv, **kwargs):
        logger.debug("BaseCollector: collect_snapshot needs to be overridden")

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
