from __future__ import absolute_import

import os
import sys
import threading

from .log import logger
from .util import every
import instana.singletons
from basictracer import Sampler
from .span import (RegisteredSpan, SDKSpan)

if sys.version_info.major == 2:
    import Queue as queue
else:
    import queue


class StandardRecorder(object):
    THREAD_NAME = "Instana Span Reporting"

    REGISTERED_SPANS = ("aiohttp-client", "aiohttp-server", "aws.lambda.entry", "cassandra", "couchbase",
                        "django", "log", "memcache", "mongo", "mysql", "postgres", "pymongo", "rabbitmq", "redis",
                        "render", "rpc-client", "rpc-server", "sqlalchemy", "soap", "tornado-client", "tornado-server",
                        "urllib3", "wsgi")

    # Recorder thread for collection/reporting of spans
    thread = None

    def __init__(self):
        self.queue = queue.Queue()

    def start(self):
        """
        This function can be called at first boot or after a fork.  In either case, it will
        assure that the Recorder is in a proper state (via reset()) and spawn a new background
        thread to periodically report queued spans

        Note that this will abandon any previous thread object that (in the case of an `os.fork()`)
        should no longer exist in the forked process.

        (Forked processes carry forward only the thread that called `os.fork()`
        into the new process space.  All other background threads need to be recreated.)

        Calling this directly more than once without an actual fork will cause errors.
        """
        self.reset()
        self.thread.start()

    def reset(self):
        # Prepare the thread for span collection/reporting
        self.thread = threading.Thread(target=self.report_spans)
        self.thread.daemon = True
        self.thread.name = self.THREAD_NAME

    def handle_fork(self):
        self.start()

    def report_spans(self):
        """ Periodically report the queued spans """
        logger.debug(" -> Span reporting thread is now alive")

        def span_work():
            if instana.singletons.agent.should_threads_shutdown.is_set():
                logger.debug("Thread shutdown signal from agent is active: Shutting down span reporting thread")
                return False

            queue_size = self.queue.qsize()
            if queue_size > 0 and instana.singletons.agent.can_send():
                response = instana.singletons.agent.report_traces(self.queued_spans())
                if response:
                    logger.debug("reported %d spans", queue_size)
            return True

        if "INSTANA_TEST" not in os.environ:
            every(2, span_work, "Span Reporting")

    def queue_size(self):
        """ Return the size of the queue; how may spans are queued, """
        return self.queue.qsize()

    def queued_spans(self):
        """ Get all of the spans in the queue """
        span = None
        spans = []
        while True:
            try:
                span = self.queue.get(False)
            except queue.Empty:
                break
            else:
                spans.append(span)
        return spans

    def clear_spans(self):
        """ Clear the queue of spans """
        self.queued_spans()

    def record_span(self, span):
        """
        Convert the passed BasicSpan into and add it to the span queue
        """
        if instana.singletons.agent.can_send() or "INSTANA_TEST" in os.environ:
            source = instana.singletons.agent.get_from_structure()

            if span.operation_name in self.REGISTERED_SPANS:
                json_span = RegisteredSpan(span, source)
            else:
                service_name = instana.singletons.agent.options.service_name
                json_span = SDKSpan(span, source, service_name)

            self.queue.put(json_span)


class AWSLambdaRecorder(StandardRecorder):
    def __init__(self, agent):
        self.agent = agent
        super(AWSLambdaRecorder, self).__init__()

    def record_span(self, span):
        """
        Convert the passed BasicSpan and add it to the span queue
        """
        source = self.agent.get_from_structure()

        if span.operation_name in self.REGISTERED_SPANS:
            json_span = RegisteredSpan(span, source)
        else:
            service_name = self.agent.options.service_name
            json_span = SDKSpan(span, source, service_name)

        # logger.debug("Recorded span: %s", json_span)
        self.agent.collector.span_queue.put(json_span)


class InstanaSampler(Sampler):
    def sampled(self, _):
        return False
