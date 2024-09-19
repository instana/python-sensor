# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016

# Accept, process and queue spans for eventual reporting.

import os
import queue
from typing import TYPE_CHECKING, List, Optional, Type

from instana.span.kind import REGISTERED_SPANS
from instana.span.readable_span import ReadableSpan
from instana.span.registered_span import RegisteredSpan
from instana.span.sdk_span import SDKSpan

if TYPE_CHECKING:
    from instana.agent.base import BaseAgent


class StanRecorder(object):
    THREAD_NAME = "InstanaSpan Recorder"

    # Recorder thread for collection/reporting of spans
    thread = None

    def __init__(self, agent: Optional[Type["BaseAgent"]] = None) -> None:
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

    def queued_spans(self) -> List[ReadableSpan]:
        """Get all of the spans in the queue."""
        span = None
        spans = []

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
        """Clear the queue of spans."""
        if not self.agent.collector.span_queue.empty():
            self.queued_spans()

    def record_span(self, span: ReadableSpan) -> None:
        """
        Convert the passed span into JSON and add it to the span queue.
        """
        if span.context.suppression:
            return

        if self.agent.can_send():
            service_name = None
            source = self.agent.get_from_structure()
            if "INSTANA_SERVICE_NAME" in os.environ:
                service_name = self.agent.options.service_name

            if span.name in REGISTERED_SPANS:
                json_span = RegisteredSpan(span, source, service_name)
            else:
                service_name = self.agent.options.service_name
                json_span = SDKSpan(span, source, service_name)

            # logger.debug("Recorded span: %s", json_span)
            self.agent.collector.span_queue.put(json_span)
