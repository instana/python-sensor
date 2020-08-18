from __future__ import absolute_import

import os
import sys

from basictracer import Sampler

from .log import logger
from .span import (RegisteredSpan, SDKSpan)

if sys.version_info.major == 2:
    import Queue as queue
else:
    import queue


class StanRecorder(object):
    THREAD_NAME = "Instana Span Reporting"

    REGISTERED_SPANS = ("aiohttp-client", "aiohttp-server", "aws.lambda.entry", "cassandra",
                        "celery-client", "celery-worker", "couchbase", "django", "log",
                        "memcache", "mongo", "mysql", "postgres", "pymongo", "rabbitmq", "redis",
                        "render", "rpc-client", "rpc-server", "sqlalchemy", "soap", "tornado-client",
                        "tornado-server", "urllib3", "wsgi")

    # Recorder thread for collection/reporting of spans
    thread = None

    def __init__(self, agent = None):
        if agent is None:
            # Late import to avoid circular import
            # pylint: disable=import-outside-toplevel
            from .singletons import get_agent
            self.agent = get_agent()
        else:
            self.agent = agent

    def queue_size(self):
        """ Return the size of the queue; how may spans are queued, """
        return self.agent.collector.span_queue.qsize()

    def queued_spans(self):
        """ Get all of the spans in the queue """
        span = None
        spans = []
        while True:
            try:
                span = self.agent.collector.span_queue.get(False)
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
        if self.agent.can_send():
            service_name = None
            source = self.agent.get_from_structure()
            if "INSTANA_SERVICE_NAME" in os.environ:
                service_name = self.agent.options.service_name

            if span.operation_name in self.REGISTERED_SPANS:
                json_span = RegisteredSpan(span, source, service_name)
            else:
                service_name = self.agent.options.service_name
                json_span = SDKSpan(span, source, service_name)

            # logger.debug("Recorded span: %s", json_span)
            self.agent.collector.span_queue.put(json_span)


class InstanaSampler(Sampler):
    def sampled(self, _):
        # We never sample
        return False
