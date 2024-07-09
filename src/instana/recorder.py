# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016

# Accept, process and queue spans for eventual reporting.

import os
import queue
from typing import List, Optional

from instana.agent.base import BaseAgent
from instana.span import InstanaSpan, RegisteredSpan, SDKSpan


class StanRecorder(object):
    THREAD_NAME = "Instana Span Reporting"

    REGISTERED_SPANS = (
        "aiohttp-client",
        "aiohttp-server",
        "aws.lambda.entry",
        "boto3",
        "cassandra",
        "celery-client",
        "celery-worker",
        "couchbase",
        "django",
        "gcs",
        "gcps-producer",
        "gcps-consumer",
        "log",
        "memcache",
        "mongo",
        "mysql",
        "postgres",
        "pymongo",
        "rabbitmq",
        "redis",
        "render",
        "rpc-client",
        "rpc-server",
        "sqlalchemy",
        "tornado-client",
        "tornado-server",
        "urllib3",
        "wsgi",
        "asgi",
    )

    # Recorder thread for collection/reporting of spans
    thread = None

    def __init__(self, agent: Optional[BaseAgent] = None) -> None:
        if agent is None:
            # Late import to avoid circular import
            # pylint: disable=import-outside-toplevel
            from instana.singletons import get_agent

            self.agent = get_agent()
        else:
            self.agent = agent

    def queue_size(self) -> int:
        """Return the size of the queue; how may spans are queued,"""
        return self.agent.collector.span_queue.qsize()

    def queued_spans(self) -> List[InstanaSpan]:
        """Get all of the spans in the queue"""
        span = None
        spans = []

        import time
        from .singletons import env_is_test

        if env_is_test is True:
            time.sleep(1)

        if self.agent.collector.span_queue.empty() is True:
            return spans

        while True:
            try:
                span = self.agent.collector.span_queue.get(False)
            except queue.Empty:
                break
            else:
                spans.append(span)
        return spans

    def clear_spans(self):
        """Clear the queue of spans"""
        if not self.agent.collector.span_queue.empty():
            self.queued_spans()

    def record_span(self, span: InstanaSpan) -> None:
        """
        Convert the passed Span into JSON and add it to the span queue
        """
        if span.context.suppression:
            return

        if self.agent.can_send():
            service_name = None
            source = self.agent.get_from_structure()
            if "INSTANA_SERVICE_NAME" in os.environ:
                service_name = self.agent.options.service_name

            if span.name in self.REGISTERED_SPANS:
                json_span = RegisteredSpan(span, source, service_name)
            else:
                service_name = self.agent.options.service_name
                json_span = SDKSpan(span, source, service_name)

            # logger.debug("Recorded span: %s", json_span)
            self.agent.collector.span_queue.put(json_span)
