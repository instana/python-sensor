from __future__ import absolute_import

import threading
import unittest
import mock
from google.auth import credentials
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from google.cloud.pubsub_v1.subscriber import message

from instana.singletons import tracer
from tests.test_utils import _TraceContextMixin


class TestPubSubPublish(unittest.TestCase, _TraceContextMixin):
    def setUp(self):
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def test_publish(self):
        creds = mock.Mock(spec=credentials.Credentials)
        client = PublisherClient(credentials=creds)

        # Use a mock in lieu of the actual batch class.
        batch = mock.Mock(spec=client._batch_class)
        topic = "projects/test-project/topics/test-topic"
        client._batches[topic] = batch

        with tracer.start_active_span('test'):
            client.publish(topic, b'message')

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


class TestPubSubSubscribe(unittest.TestCase, _TraceContextMixin):
    def setUp(self):
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def test_consume(self):
        def handle_message(msg):
            print(message.data)
            msg.ack()

        def __consume():

            with tracer.start_active_span('test'):
                future = pub_client.publish(topic, b'message')
                future.result(timeout=5)

            future = sub_client.subscribe(subscription_path, handle_message)
            try:
                future.result(timeout=5)
            except Exception as e:
                print("something BAD happened")
                raise

        creds = mock.Mock(spec=credentials.Credentials)
        pub_client = PublisherClient(credentials=creds)
        sub_client = SubscriberClient(credentials=creds)

        # Use a mock in lieu of the actual batch class.
        batch = mock.Mock(spec=pub_client._batch_class)
        topic = "projects/test-project/topics/test-topic"
        project_id = 'k8s-brewery'
        subscription_id = 'python-test-subscription'
        subscription_path = sub_client.subscription_path(project_id, subscription_id)
        pub_client._batches[topic] = batch

        # Create a topic & subscription attached to the topic
        ct = mock.Mock()
        pub_client.api._inner_api_calls["create_topic"] = ct
        pub_client.create_topic(topic)

        cx = mock.Mock()
        sub_client.api._inner_api_calls["create_subscription"] = cx
        sub_client.create_subscription(subscription_path, topic)

        t = threading.Thread(target=__consume)
        t.start()
        t.join(timeout=5)

        spans = self.recorder.queued_spans()
        # print(spans)
        span_1 = spans[0]
        span_2 = spans[1]
        # print(span_1)
        # print(span_2)
        self.assertEqual(3, len(spans))  # this fails
