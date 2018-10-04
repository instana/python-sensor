from __future__ import absolute_import

import asyncio
import os
import sys
import unittest

import asynqp

from instana.singletons import tracer

rabbitmq_host = ""
if "RABBITMQ_HOST" in os.environ:
    rabbitmq_host = os.environ["RABBITMQ_HOST"]
else:
    rabbitmq_host = "localhost"

class TestAsynqp(unittest.TestCase):
    @asyncio.coroutine
    def connect(self):
        # connect to the RabbitMQ broker
        self.connection = yield from asynqp.connect(rabbitmq_host, 5672, username='guest', password='guest')

        # Open a communications channel
        self.channel = yield from self.connection.open_channel()

        # Create a queue and an exchange on the broker
        self.exchange = yield from self.channel.declare_exchange('test.exchange', 'direct')
        self.queue = yield from self.channel.declare_queue('test.queue')

        # Bind the queue to the exchange, so the queue will get messages published to the exchange
        yield from self.queue.bind(self.exchange, 'routing.key')
        yield from self.queue.purge()

    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

        # New event loop for every test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.loop.run_until_complete(self.connect())

    def tearDown(self):
        """ Purge the queue """
        self.queue.purge()
        self.queue.delete(if_unused=False, if_empty=False)

    def test_publish(self):
        @asyncio.coroutine
        def test():
            with tracer.start_active_span('test'):
                msg = asynqp.Message({'hello': 'world'})
                self.exchange.publish(msg, 'routing.key')

        self.loop.run_until_complete(test())

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
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(rabbitmq_span.error)
        self.assertIsNone(rabbitmq_span.ec)

        # Rabbitmq
        self.assertEqual('test.exchange', rabbitmq_span.data.rabbitmq.exchange)
        self.assertEqual('publish', rabbitmq_span.data.rabbitmq.sort)
        self.assertIsNotNone(rabbitmq_span.data.rabbitmq.address)
        self.assertEqual('routing.key', rabbitmq_span.data.rabbitmq.key)

    def test_get(self):
        @asyncio.coroutine
        def test():
            with tracer.start_active_span('test'):
                received_message = yield from self.queue.get()

        self.loop.run_until_complete(test())

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
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(rabbitmq_span.error)
        self.assertIsNone(rabbitmq_span.ec)

        # Rabbitmq
        self.assertEqual('test.queue', rabbitmq_span.data.rabbitmq.queue)
        self.assertEqual('consume', rabbitmq_span.data.rabbitmq.sort)
        self.assertIsNotNone(rabbitmq_span.data.rabbitmq.address)

    def test_consume(self):
        def handle_message(msg):
            print('>> {}'.format(msg.body))
            msg.ack()

        @asyncio.coroutine
        def test():
            with tracer.start_active_span('test'):
                msg1 = asynqp.Message({'consume': 'this'})
                self.exchange.publish(msg1, 'routing.key')

            yield from self.queue.consume(handle_message)
            yield from asyncio.sleep(0.5)

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        publish_span = spans[0]
        test_span = spans[1]
        consume_span = spans[2]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, publish_span.t)
        self.assertEqual(test_span.t, consume_span.t)

        # Parent relationships
        self.assertEqual(publish_span.p, test_span.s)
        self.assertEqual(consume_span.p, publish_span.s)

        # publish
        self.assertEqual('test.exchange', publish_span.data.rabbitmq.exchange)
        self.assertEqual('publish', publish_span.data.rabbitmq.sort)
        self.assertIsNotNone(publish_span.data.rabbitmq.address)
        self.assertEqual('routing.key', publish_span.data.rabbitmq.key)

        # consume
        self.assertEqual('test.exchange', consume_span.data.rabbitmq.exchange)
        self.assertEqual('consume', consume_span.data.rabbitmq.sort)
        self.assertIsNotNone(consume_span.data.rabbitmq.address)
        self.assertEqual('routing.key', consume_span.data.rabbitmq.key)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(consume_span.error)
        self.assertIsNone(consume_span.ec)
        self.assertFalse(publish_span.error)
        self.assertIsNone(publish_span.ec)
