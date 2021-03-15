# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from __future__ import absolute_import

import os
import pika
import unittest
import mock
import threading
import time

from ..helpers import testenv
from instana.singletons import tracer

class _TestPika(unittest.TestCase):
    @staticmethod
    @mock.patch('pika.connection.Connection')
    def _create_connection(connection_class_mock=None):
        return connection_class_mock()

    def _create_obj(self):
        raise NotImplementedError()

    def setUp(self):
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

        self.connection = self._create_connection()
        self._on_openok_callback = mock.Mock()
        self.obj = self._create_obj()

    def tearDown(self):
        del self.connection
        del self._on_openok_callback
        del self.obj

class TestPikaChannel(_TestPika):
    def _create_obj(self):
        return pika.channel.Channel(self.connection, 1, self._on_openok_callback)

    @mock.patch('pika.spec.Basic.Publish')
    @mock.patch('pika.channel.Channel._send_method')
    def test_basic_publish(self, send_method, _unused):
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
                routing_key="test.queue"), (pika.spec.BasicProperties(headers={
                    "X-INSTANA-T": rabbitmq_span.t,
                    "X-INSTANA-S": rabbitmq_span.s,
                    "X-INSTANA-L": "1"
                }), b"Hello!"))

    @mock.patch('pika.spec.Basic.Publish')
    @mock.patch('pika.channel.Channel._send_method')
    def test_basic_publish_with_headers(self, send_method, _unused):
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
                routing_key="test.queue"), (pika.spec.BasicProperties(headers={
                    "X-Custom-1": "test",
                    "X-INSTANA-T": rabbitmq_span.t,
                    "X-INSTANA-S": rabbitmq_span.s,
                    "X-INSTANA-L": "1"
                }), b"Hello!"))

    @mock.patch('pika.spec.Basic.Get')
    def test_basic_get(self, _unused):
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        properties = pika.BasicProperties()

        method_frame = pika.frame.Method(1, pika.spec.Basic.GetOk)
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_get("test.queue", cb)
        self.obj._on_getok(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        rabbitmq_span = spans[0]

        self.assertIsNone(tracer.active_span)

        # A new span has been started
        self.assertIsNotNone(rabbitmq_span.t)
        self.assertIsNone(rabbitmq_span.p)
        self.assertIsNotNone(rabbitmq_span.s)

        # Error logging
        self.assertIsNone(rabbitmq_span.ec)

        # Span tags
        self.assertIsNone(rabbitmq_span.data["rabbitmq"]["exchange"])
        self.assertEqual("consume", rabbitmq_span.data["rabbitmq"]["sort"])
        self.assertIsNotNone(rabbitmq_span.data["rabbitmq"]["address"])
        self.assertEqual("test.queue", rabbitmq_span.data["rabbitmq"]["queue"])
        self.assertIsNotNone(rabbitmq_span.stack)
        self.assertTrue(type(rabbitmq_span.stack) is list)
        self.assertGreater(len(rabbitmq_span.stack), 0)

        cb.assert_called_once_with(self.obj, pika.spec.Basic.GetOk, properties, body)

    @mock.patch('pika.spec.Basic.Get')
    def test_basic_get_with_trace_context(self, _unused):
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        properties = pika.BasicProperties(headers={
            "X-INSTANA-T": "0000000000000001",
            "X-INSTANA-S": "0000000000000002",
            "X-INSTANA-L": "1"
        })

        method_frame = pika.frame.Method(1, pika.spec.Basic.GetOk)
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_get("test.queue", cb)
        self.obj._on_getok(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        rabbitmq_span = spans[0]

        self.assertIsNone(tracer.active_span)

        # Trace context propagation
        self.assertEqual("0000000000000001", rabbitmq_span.t)
        self.assertEqual("0000000000000002", rabbitmq_span.p)

        # A new span has been started
        self.assertIsNotNone(rabbitmq_span.s)
        self.assertNotEqual(rabbitmq_span.p, rabbitmq_span.s)

    @mock.patch('pika.spec.Basic.Consume')
    def test_basic_consume(self, _unused):
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        properties = pika.BasicProperties()

        method_frame = pika.frame.Method(1, pika.spec.Basic.Deliver(consumer_tag="test"))
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_consume("test.queue", cb, consumer_tag="test")
        self.obj._on_deliver(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        rabbitmq_span = spans[0]

        self.assertIsNone(tracer.active_span)

        # A new span has been started
        self.assertIsNotNone(rabbitmq_span.t)
        self.assertIsNone(rabbitmq_span.p)
        self.assertIsNotNone(rabbitmq_span.s)

        # Error logging
        self.assertIsNone(rabbitmq_span.ec)

        # Span tags
        self.assertIsNone(rabbitmq_span.data["rabbitmq"]["exchange"])
        self.assertEqual("consume", rabbitmq_span.data["rabbitmq"]["sort"])
        self.assertIsNotNone(rabbitmq_span.data["rabbitmq"]["address"])
        self.assertEqual("test.queue", rabbitmq_span.data["rabbitmq"]["queue"])
        self.assertIsNotNone(rabbitmq_span.stack)
        self.assertTrue(type(rabbitmq_span.stack) is list)
        self.assertGreater(len(rabbitmq_span.stack), 0)

        cb.assert_called_once_with(self.obj, method_frame.method, properties, body)

    @mock.patch('pika.spec.Basic.Consume')
    def test_basic_consume_with_trace_context(self, _unused):
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        properties = pika.BasicProperties(headers={
            "X-INSTANA-T": "0000000000000001",
            "X-INSTANA-S": "0000000000000002",
            "X-INSTANA-L": "1"
        })

        method_frame = pika.frame.Method(1, pika.spec.Basic.Deliver(consumer_tag="test"))
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_consume("test.queue", cb, consumer_tag="test")
        self.obj._on_deliver(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        rabbitmq_span = spans[0]

        self.assertIsNone(tracer.active_span)

        # Trace context propagation
        self.assertEqual("0000000000000001", rabbitmq_span.t)
        self.assertEqual("0000000000000002", rabbitmq_span.p)

        # A new span has been started
        self.assertIsNotNone(rabbitmq_span.s)
        self.assertNotEqual(rabbitmq_span.p, rabbitmq_span.s)

class TestPikaBlockingChannel(_TestPika):
    @mock.patch('pika.channel.Channel', spec=pika.channel.Channel)
    def _create_obj(self, channel_impl):
        self.impl = channel_impl()
        self.impl.channel_number = 1

        return pika.adapters.blocking_connection.BlockingChannel(self.impl, self.connection)

    def _generate_delivery(self, consumer_tag, properties, body):
        from pika.adapters.blocking_connection import _ConsumerDeliveryEvt

        # Wait until queue consumer is initialized
        while self.obj._queue_consumer_generator is None:
            time.sleep(0.25)

        method = pika.spec.Basic.Deliver(consumer_tag=consumer_tag)
        self.obj._on_consumer_generator_event(_ConsumerDeliveryEvt(method, properties, body))

    def test_consume(self):
        consumed_deliveries = []
        def __consume():
            for delivery in self.obj.consume("test.queue", inactivity_timeout=3.0):
                # Skip deliveries generated due to inactivity
                if delivery is not None and any(delivery):
                    consumed_deliveries.append(delivery)

                break

        consumer_tag = "test.consumer"

        self.impl.basic_consume.return_value = consumer_tag
        self.impl._generate_consumer_tag.return_value = consumer_tag
        self.impl._consumers = {}

        t = threading.Thread(target=__consume)
        t.start()

        self._generate_delivery(consumer_tag, pika.BasicProperties(), "Hello!")

        t.join(timeout=5.0)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        rabbitmq_span = spans[0]

        self.assertIsNone(tracer.active_span)

        # A new span has been started
        self.assertIsNotNone(rabbitmq_span.t)
        self.assertIsNone(rabbitmq_span.p)
        self.assertIsNotNone(rabbitmq_span.s)

        # Error logging
        self.assertIsNone(rabbitmq_span.ec)

        # Span tags
        self.assertIsNone(rabbitmq_span.data["rabbitmq"]["exchange"])
        self.assertEqual("consume", rabbitmq_span.data["rabbitmq"]["sort"])
        self.assertIsNotNone(rabbitmq_span.data["rabbitmq"]["address"])
        self.assertEqual("test.queue", rabbitmq_span.data["rabbitmq"]["queue"])
        self.assertIsNotNone(rabbitmq_span.stack)
        self.assertTrue(type(rabbitmq_span.stack) is list)
        self.assertGreater(len(rabbitmq_span.stack), 0)

        self.assertEqual(1, len(consumed_deliveries))

    def test_consume_with_trace_context(self):
        consumed_deliveries = []
        def __consume():
            for delivery in self.obj.consume("test.queue", inactivity_timeout=3.0):
                # Skip deliveries generated due to inactivity
                if delivery is not None and any(delivery):
                    consumed_deliveries.append(delivery)

                break

        consumer_tag = "test.consumer"

        self.impl.basic_consume.return_value = consumer_tag
        self.impl._generate_consumer_tag.return_value = consumer_tag
        self.impl._consumers = {}

        t = threading.Thread(target=__consume)
        t.start()

        self._generate_delivery(consumer_tag, pika.BasicProperties(headers={
            "X-INSTANA-T": "0000000000000001",
            "X-INSTANA-S": "0000000000000002",
            "X-INSTANA-L": "1"
        }), "Hello!")

        t.join(timeout=5.0)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        rabbitmq_span = spans[0]

        self.assertIsNone(tracer.active_span)

        # Trace context propagation
        self.assertEqual("0000000000000001", rabbitmq_span.t)
        self.assertEqual("0000000000000002", rabbitmq_span.p)

        # A new span has been started
        self.assertIsNotNone(rabbitmq_span.s)
        self.assertNotEqual(rabbitmq_span.p, rabbitmq_span.s)
