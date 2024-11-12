# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import os
import threading
import time
from typing import Generator

import pytest
import six
from google.api_core.exceptions import AlreadyExists
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from google.cloud.pubsub_v1.publisher import exceptions
from opentelemetry.trace import SpanKind

from instana.singletons import agent, tracer
from instana.span.span import get_current_span
from tests.test_utils import _TraceContextMixin

# Use PubSub Emulator exposed at :8085
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8681"


class TestPubSubPublish(_TraceContextMixin):
    publisher = PublisherClient()

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        self.project_id = "test-project"
        self.topic_name = "test-topic"

        # setup topic_path & topic
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
        try:
            self.publisher.create_topic(request={"name": self.topic_path})
        except AlreadyExists:
            self.publisher.delete_topic(request={"topic": self.topic_path})
            self.publisher.create_topic(request={"name": self.topic_path})
        yield
        self.publisher.delete_topic(request={"topic": self.topic_path})
        agent.options.allow_exit_as_root = False

    def test_publish(self) -> None:
        # publish a single message
        with tracer.start_as_current_span("test"):
            future = self.publisher.publish(
                self.topic_path, b"Test Message", origin="instana"
            )
        time.sleep(2.0)  # for sanity
        result = future.result()
        assert isinstance(result, six.string_types)

        spans = self.recorder.queued_spans()
        gcps_span, test_span = spans[0], spans[1]

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()
        assert gcps_span.n == "gcps"
        assert gcps_span.k is SpanKind.CLIENT

        assert gcps_span.data["gcps"]["op"] == "publish"
        assert self.topic_name == gcps_span.data["gcps"]["top"]

        # Trace Context Propagation
        self.assertTraceContextPropagated(test_span, gcps_span)

        # Error logging
        self.assertErrorLogging(spans)

    def test_publish_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        # publish a single message
        future = self.publisher.publish(
            self.topic_path, b"Test Message", origin="instana"
        )
        time.sleep(2.0)  # for sanity
        result = future.result()
        assert isinstance(result, six.string_types)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        gcps_span = spans[0]

        current_span = get_current_span()
        assert not current_span.is_recording()
        assert gcps_span.n == "gcps"
        assert gcps_span.k is SpanKind.CLIENT

        assert gcps_span.data["gcps"]["op"] == "publish"
        assert self.topic_name == gcps_span.data["gcps"]["top"]

        # Error logging
        self.assertErrorLogging(spans)


class AckCallback(object):
    def __init__(self) -> None:
        self.calls = 0
        self.lock = threading.Lock()

    def __call__(self, message) -> None:
        message.ack()
        # Only increment the number of calls **after** finishing.
        with self.lock:
            self.calls += 1


class TestPubSubSubscribe(_TraceContextMixin):
    @classmethod
    def setup_class(cls) -> None:
        cls.publisher = PublisherClient()
        cls.subscriber = SubscriberClient()

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        self.project_id = "test-project"
        self.topic_name = "test-topic"
        self.subscription_name = "test-subscription"

        # setup topic_path & topic
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
        try:
            self.publisher.create_topic(request={"name": self.topic_path})
        except AlreadyExists:
            self.publisher.delete_topic(request={"topic": self.topic_path})
            self.publisher.create_topic(request={"name": self.topic_path})

        # setup subscription path & attach subscription
        self.subscription_path = self.subscriber.subscription_path(
            self.project_id,
            self.subscription_name,
        )
        try:
            self.subscriber.create_subscription(
                request={"name": self.subscription_path, "topic": self.topic_path}
            )
        except AlreadyExists:
            self.subscriber.delete_subscription(
                request={"subscription": self.subscription_path}
            )
            self.subscriber.create_subscription(
                request={"name": self.subscription_path, "topic": self.topic_path}
            )
        yield
        self.publisher.delete_topic(request={"topic": self.topic_path})
        self.subscriber.delete_subscription(
            request={"subscription": self.subscription_path}
        )

    def test_subscribe(self) -> None:
        with tracer.start_as_current_span("test"):
            # Publish a message
            future = self.publisher.publish(
                self.topic_path, b"Test Message to PubSub", origin="instana"
            )
            assert isinstance(future.result(), six.string_types)

            time.sleep(2.0)  # for sanity

            # Subscribe to the subscription
            callback_handler = AckCallback()
            future = self.subscriber.subscribe(self.subscription_path, callback_handler)
            timeout = 2.0
            try:
                future.result(timeout)
            except exceptions.TimeoutError:
                future.cancel()

        spans = self.recorder.queued_spans()

        producer_span = spans[0]
        consumer_span = spans[1]
        test_span = spans[2]

        assert len(spans) == 3
        current_span = get_current_span()
        assert not current_span.is_recording()
        assert producer_span.data["gcps"]["op"] == "publish"
        assert consumer_span.data["gcps"]["op"] == "consume"
        assert self.topic_name == producer_span.data["gcps"]["top"]
        assert self.subscription_name == consumer_span.data["gcps"]["sub"]

        assert producer_span.k is SpanKind.CLIENT
        assert consumer_span.k is SpanKind.SERVER

        # Trace Context Propagation
        self.assertTraceContextPropagated(producer_span, consumer_span)
        self.assertTraceContextPropagated(test_span, producer_span)

        # Error logging
        self.assertErrorLogging(spans)
