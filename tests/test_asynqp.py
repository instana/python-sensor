from __future__ import absolute_import

import asyncio
import os
import unittest

import asynqp

from instana.singletons import async_tracer

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

    @asyncio.coroutine
    def reset(self):
        yield from self.queue.delete(if_unused=False, if_empty=False)

    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = async_tracer.recorder
        self.recorder.clear_spans()

        # New event loop for every test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.loop.run_until_complete(self.connect())

    def tearDown(self):
        """ Purge the queue """
        self.loop.run_until_complete(self.reset())

    def test_publish(self):
        @asyncio.coroutine
        def test():
            with async_tracer.start_active_span('test'):
                msg = asynqp.Message({'hello': 'world'})
                self.exchange.publish(msg, 'routing.key')

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        rabbitmq_span = spans[0]
        test_span = spans[1]

        self.assertIsNone(async_tracer.active_span)

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
        self.assertIsNotNone(rabbitmq_span.stack)
        self.assertTrue(type(rabbitmq_span.stack) is list)
        self.assertGreater(len(rabbitmq_span.stack), 0)

    def test_get(self):
        @asyncio.coroutine
        def publish():
            with async_tracer.start_active_span('test'):
                msg1 = asynqp.Message({'consume': 'this'})
                self.exchange.publish(msg1, 'routing.key')
                asyncio.sleep(0.5)
                msg = yield from self.queue.get()
                self.assertIsNotNone(msg)

        self.loop.run_until_complete(publish())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        publish_span = spans[0]
        get_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, publish_span.t)
        self.assertEqual(test_span.t, get_span.t)

        # Parent relationships
        self.assertEqual(publish_span.p, test_span.s)
        self.assertEqual(get_span.p, test_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(publish_span.error)
        self.assertIsNone(publish_span.ec)
        self.assertFalse(get_span.error)
        self.assertIsNone(get_span.ec)

        # Publish
        self.assertEqual('publish', publish_span.data.rabbitmq.sort)
        self.assertIsNotNone(publish_span.data.rabbitmq.address)
        self.assertIsNotNone(publish_span.stack)
        self.assertTrue(type(publish_span.stack) is list)
        self.assertGreater(len(publish_span.stack), 0)

        # get
        self.assertEqual('test.queue', get_span.data.rabbitmq.queue)
        self.assertEqual('consume', get_span.data.rabbitmq.sort)
        self.assertIsNotNone(get_span.data.rabbitmq.address)
        self.assertIsNotNone(get_span.stack)
        self.assertTrue(type(get_span.stack) is list)
        self.assertGreater(len(get_span.stack), 0)

    def test_consume(self):
        def handle_message(msg):
            # print('>> {}'.format(msg.body))
            msg.ack()

        @asyncio.coroutine
        def test():
            with async_tracer.start_active_span('test'):
                msg1 = asynqp.Message({'consume': 'this'})
                self.exchange.publish(msg1, 'routing.key')

            self.consumer = yield from self.queue.consume(handle_message)
            yield from asyncio.sleep(0.5)
            self.consumer.cancel()

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        publish_span = spans[0]
        test_span = spans[1]
        consume_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

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
        self.assertIsNotNone(publish_span.stack)
        self.assertTrue(type(publish_span.stack) is list)
        self.assertGreater(len(publish_span.stack), 0)

        # consume
        self.assertEqual('test.exchange', consume_span.data.rabbitmq.exchange)
        self.assertEqual('consume', consume_span.data.rabbitmq.sort)
        self.assertIsNotNone(consume_span.data.rabbitmq.address)
        self.assertEqual('routing.key', consume_span.data.rabbitmq.key)
        self.assertIsNotNone(consume_span.stack)
        self.assertTrue(type(consume_span.stack) is list)
        self.assertGreater(len(consume_span.stack), 0)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(consume_span.error)
        self.assertIsNone(consume_span.ec)
        self.assertFalse(publish_span.error)
        self.assertIsNone(publish_span.ec)

    def test_consume_and_publish(self):
        def handle_message(msg):
            self.assertIsNotNone(msg)
            msg.ack()
            msg2 = asynqp.Message({'handled': 'msg1'})
            self.exchange.publish(msg2, 'another.key')

        @asyncio.coroutine
        def test():
            with async_tracer.start_active_span('test'):
                msg1 = asynqp.Message({'consume': 'this'})
                self.exchange.publish(msg1, 'routing.key')

                self.consumer = yield from self.queue.consume(handle_message)
                yield from asyncio.sleep(0.5)

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))

        publish1_span = spans[0]
        consume1_span = spans[1]
        publish2_span = spans[2]
        consume2_span = spans[3]
        test_span = spans[4]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, publish1_span.t)
        self.assertEqual(test_span.t, publish2_span.t)
        self.assertEqual(test_span.t, consume1_span.t)
        self.assertEqual(test_span.t, consume2_span.t)

        # Parent relationships
        self.assertEqual(publish1_span.p, test_span.s)
        self.assertEqual(publish2_span.p, test_span.s)
        self.assertEqual(consume1_span.p, publish1_span.s)
        self.assertEqual(consume2_span.p, publish2_span.s)

        # publish
        self.assertEqual('test.exchange', publish1_span.data.rabbitmq.exchange)
        self.assertEqual('publish', publish1_span.data.rabbitmq.sort)
        self.assertIsNotNone(publish1_span.data.rabbitmq.address)
        self.assertEqual('routing.key', publish1_span.data.rabbitmq.key)
        self.assertIsNotNone(publish1_span.stack)
        self.assertTrue(type(publish1_span.stack) is list)
        self.assertGreater(len(publish1_span.stack), 0)

        self.assertEqual('test.exchange', publish2_span.data.rabbitmq.exchange)
        self.assertEqual('publish', publish2_span.data.rabbitmq.sort)
        self.assertIsNotNone(publish2_span.data.rabbitmq.address)
        self.assertEqual('another.key', publish2_span.data.rabbitmq.key)
        self.assertIsNotNone(publish2_span.stack)
        self.assertTrue(type(publish2_span.stack) is list)
        self.assertGreater(len(publish2_span.stack), 0)

        # consume
        self.assertEqual('test.exchange', consume1_span.data.rabbitmq.exchange)
        self.assertEqual('consume', consume1_span.data.rabbitmq.sort)
        self.assertIsNotNone(consume1_span.data.rabbitmq.address)
        self.assertEqual('routing.key', consume1_span.data.rabbitmq.key)
        self.assertIsNotNone(consume1_span.stack)
        self.assertTrue(type(consume1_span.stack) is list)
        self.assertGreater(len(consume1_span.stack), 0)

        self.assertEqual('test.exchange', consume2_span.data.rabbitmq.exchange)
        self.assertEqual('consume', consume2_span.data.rabbitmq.sort)
        self.assertIsNotNone(consume2_span.data.rabbitmq.address)
        self.assertEqual('another.key', consume2_span.data.rabbitmq.key)
        self.assertIsNotNone(consume2_span.stack)
        self.assertTrue(type(consume2_span.stack) is list)
        self.assertGreater(len(consume2_span.stack), 0)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(consume1_span.error)
        self.assertIsNone(consume1_span.ec)
        self.assertFalse(consume2_span.error)
        self.assertIsNone(consume2_span.ec)
        self.assertFalse(publish1_span.error)
        self.assertIsNone(publish1_span.ec)
        self.assertFalse(publish2_span.error)
        self.assertIsNone(publish2_span.ec)
