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
            logger.warn("Collector started but the agent tells us we can't send anything out.")

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

    def prepare_and_report_data(self):
        lock_acquired = self.lock.acquire(False)
        if lock_acquired:
            payload = stan_dictionary()

            if not self.span_queue.empty():
                payload["spans"] = self.__queued_spans()

                if self.snapshot_data and self.snapshot_data_sent is False:
                    payload["metrics"] = self.snapshot_data
                    self.snapshot_data_sent = True

            if len(payload) > 0:
                logger.debug(to_json(payload))
                self.agent.report_data_payload(payload)
            else:
                logger.debug("prepare_and_report_data: No data to report")
            self.lock.release()
        else:
            logger.debug("prepare_and_report_data: Couldn't acquire lock")
        return True

    def collect_snapshot(self, event, context):
        self.snapshot_data = stan_dictionary()
        metrics = stan_dictionary()

        self.context = context
        self.event = event

        try:
            metrics["name"] = "com.instana.plugin.aws.lambda"
            metrics["entityId"] = self.context.invoked_function_arn
            self.snapshot_data["plugins"] = [metrics]
        except:
            logger.debug("collect_snapshot error", exc_info=True)


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
