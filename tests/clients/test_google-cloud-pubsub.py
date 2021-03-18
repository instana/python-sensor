from __future__ import absolute_import

import os
import six
import unittest

from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from instana.singletons import tracer
from tests.test_utils import _TraceContextMixin

# Use PubSub Emulator exposed at :8432
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8432"


class TestPubSubPublish(unittest.TestCase, _TraceContextMixin):
    @classmethod
    def setUpClass(cls):
        cls.publisher = PublisherClient()
        cls.project_id = 'test-project'
        cls.topic_name = 'test-topic'

    def setUp(self):
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

        # setup topic_path & topic
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_name)
        self.publisher.create_topic(self.topic_path)

    def tearDown(self):
        self.publisher.delete_topic(self.topic_path)

    def test_publish(self):
        # publish a single message
        with tracer.start_active_span('test'):
            future = self.publisher.publish(self.topic_path, b'message')

        result = future.result()
        assert isinstance(result, six.string_types)

        spans = self.recorder.queued_spans()
        gcps_span, test_span = spans[0], spans[1]

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)
        self.assertEqual('gcps', gcps_span.n)
        self.assertEqual(2, gcps_span.k)  # EXIT
        self.assertIsNone(gcps_span.ec)

        self.assertEqual('publish', gcps_span.data['gcps']['op'])
        self.assertEqual('test-topic', gcps_span.data['gcps']['top'])

        # Trace Context Propagation
        self.assertTraceContextPropagated(test_span, gcps_span)

