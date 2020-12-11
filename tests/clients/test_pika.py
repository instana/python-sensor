from __future__ import absolute_import

import os
import pika
import unittest
import mock

from ..helpers import testenv
from instana.singletons import tracer

class TestPika(unittest.TestCase):
    @staticmethod
    @mock.patch('pika.connection.Connection')
    def _create_connection(connection_class_mock=None):
        return connection_class_mock()

    def setUp(self):
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

        self.connection = self._create_connection()
        self._on_openok_callback = mock.Mock()
        self.obj = pika.channel.Channel(self.connection, 1,
                                   self._on_openok_callback)

    def tearDown(self):
        del self.connection
        del self._on_openok_callback
        del self.obj

    @mock.patch('pika.spec.Basic.Publish')
    @mock.patch('pika.channel.Channel._send_method')
    def test_Channel_basic_publish(self, send_method, _unused):
        self.obj._set_state(self.obj.OPEN)

        with tracer.start_active_span("testing"):
            self.obj.basic_publish("test.exchange", "test.queue", "Hello!")

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        rabbitmq_span = spans[0]
        test_span = spans[1]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, rabbitmq_span.t)

        # Parent relationships
        self.assertEqual(rabbitmq_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(rabbitmq_span.ec)

        # Span tags
        self.assertEqual("test.exchange", rabbitmq_span.data["rabbitmq"]["exchange"])
        self.assertEqual('publish', rabbitmq_span.data["rabbitmq"]["sort"])
        self.assertIsNotNone(rabbitmq_span.data["rabbitmq"]["address"])
        self.assertEqual("test.queue", rabbitmq_span.data["rabbitmq"]["key"])
        self.assertIsNotNone(rabbitmq_span.stack)
        self.assertTrue(type(rabbitmq_span.stack) is list)
        self.assertGreater(len(rabbitmq_span.stack), 0)

        send_method.assert_called_once_with(
            pika.spec.Basic.Publish(
                exchange="test.exchange",
                routing_key="test.queue"), (pika.BasicProperties(headers={
                    "X-Instana-T": rabbitmq_span.t,
                    "X-Instana-S": rabbitmq_span.s,
                    "X-Instana-L": "1"
                }), b"Hello!"))

    @mock.patch('pika.spec.Basic.Publish')
    @mock.patch('pika.channel.Channel._send_method')
    def test_Channel_basic_publish_with_headers(self, send_method, _unused):
        self.obj._set_state(self.obj.OPEN)

        with tracer.start_active_span("testing"):
            self.obj.basic_publish("test.exchange",
                                   "test.queue",
                                   "Hello!",
                                   pika.BasicProperties(headers={
                                       "X-Custom-1": "test"
                                   }))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        rabbitmq_span = spans[0]
        test_span = spans[1]

        send_method.assert_called_once_with(
            pika.spec.Basic.Publish(
                exchange="test.exchange",
                routing_key="test.queue"), (pika.BasicProperties(headers={
                    "X-Custom-1": "test",
                    "X-Instana-T": rabbitmq_span.t,
                    "X-Instana-S": rabbitmq_span.s,
                    "X-Instana-L": "1"
                }), b"Hello!"))
