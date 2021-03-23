# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from __future__ import absolute_import

import os
import sys
import threading
import time
import pytest

import six
import unittest

from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from google.api_core.exceptions import AlreadyExists
from google.cloud.pubsub_v1.publisher import exceptions
from instana.singletons import tracer
from tests.test_utils import _TraceContextMixin

# Use PubSub Emulator exposed at :8432
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8432"


@pytest.mark.skipif(sys.version_info[0] < 3,
                    reason="google-cloud-pubsub has dropped support for Python 2")
class TestPubSubPublish(unittest.TestCase, _TraceContextMixin):
    @classmethod
    def setUpClass(cls):
        cls.publisher = PublisherClient()

    def setUp(self):
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

        self.project_id = 'test-project'
        self.topic_name = 'test-topic'

        # setup topic_path & topic
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
        try:
            self.publisher.create_topic(request={"name": self.topic_path})
        except AlreadyExists:
            self.publisher.delete_topic(request={"topic": self.topic_path})
            self.publisher.create_topic(request={"name": self.topic_path})

    def tearDown(self):
        self.publisher.delete_topic(request={"topic": self.topic_path})

    def test_publish(self):
        # publish a single message
        with tracer.start_active_span('test'):
            future = self.publisher.publish(self.topic_path,
                                            b'Test Message',
                                            origin="instana")
        time.sleep(2.0)  # for sanity
        result = future.result()
        assert isinstance(result, six.string_types)

        spans = self.recorder.queued_spans()
        gcps_span, test_span = spans[0], spans[1]

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)
        self.assertEqual('gcps', gcps_span.n)
        self.assertEqual(2, gcps_span.k)  # EXIT

        self.assertEqual('publish', gcps_span.data['gcps']['op'])
        self.assertEqual(self.topic_name, gcps_span.data['gcps']['top'])

        # Trace Context Propagation
        self.assertTraceContextPropagated(test_span, gcps_span)

        # Error logging
        self.assertErrorLogging(spans)


class AckCallback(object):
    def __init__(self):
        self.calls = 0
        self.lock = threading.Lock()

    def __call__(self, message):
        message.ack()
        # Only increment the number of calls **after** finishing.
        with self.lock:
            self.calls += 1


@pytest.mark.skipif(sys.version_info[0] < 3,
                    reason="google-cloud-pubsub has dropped support for Python 2")
class TestPubSubSubscribe(unittest.TestCase, _TraceContextMixin):
    @classmethod
    def setUpClass(cls):
        cls.publisher = PublisherClient()
        cls.subscriber = SubscriberClient()

    def setUp(self):

        self.recorder = tracer.recorder
        self.recorder.clear_spans()

        self.project_id = 'test-project'
        self.topic_name = 'test-topic'
        self.subscription_name = 'test-subscription'

        # setup topic_path & topic
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
        try:
            self.publisher.create_topic(request={"name": self.topic_path})
        except AlreadyExists:
            self.publisher.delete_topic(request={"topic": self.topic_path})
            self.publisher.create_topic(request={"name": self.topic_path})

        # setup subscription path & attach subscription
        self.subscription_path = self.subscriber.subscription_path(
            self.project_id, self.subscription_name)
        try:
            self.subscriber.create_subscription(
                request={"name": self.subscription_path, "topic": self.topic_path}
            )
        except AlreadyExists:
            self.subscriber.delete_subscription(request={"subscription": self.subscription_path})
            self.subscriber.create_subscription(
                request={"name": self.subscription_path, "topic": self.topic_path}
            )

    def tearDown(self):
        self.publisher.delete_topic(request={"topic": self.topic_path})
        self.subscriber.delete_subscription(request={"subscription": self.subscription_path})

    def test_subscribe(self):

        with tracer.start_active_span('test'):
            # Publish a message
            future = self.publisher.publish(self.topic_path,
                                            b"Test Message to PubSub",
                                            origin="instana")
            self.assertIsInstance(future.result(), six.string_types)

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

        self.assertEqual(3, len(spans))
        self.assertIsNone(tracer.active_span)
        self.assertEqual('publish', producer_span.data['gcps']['op'])
        self.assertEqual('consume', consumer_span.data['gcps']['op'])
        self.assertEqual(self.topic_name, producer_span.data['gcps']['top'])
        self.assertEqual(self.subscription_name, consumer_span.data['gcps']['sub'])

        self.assertEqual(2, producer_span.k)  # EXIT
        self.assertEqual(1, consumer_span.k)  # ENTRY

        # Trace Context Propagation
        self.assertTraceContextPropagated(producer_span, consumer_span)
        self.assertTraceContextPropagated(test_span, producer_span)

        # Error logging
        self.assertErrorLogging(spans)
