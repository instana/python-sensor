from __future__ import absolute_import

import asyncio
import unittest

import asynqp
from instana.singletons import tracer


class TestAsynqp(unittest.TestCase):
    @asyncio.coroutine
    def connect(self):
        # connect to the RabbitMQ broker
        self.connection = yield from asynqp.connect('192.168.201.129', 5672, username='guest', password='guest')

        # Open a communications channel
        self.channel = yield from self.connection.open_channel()

        # Create a queue and an exchange on the broker
        self.exchange = yield from self.channel.declare_exchange('test.exchange', 'direct')
        self.queue = yield from self.channel.declare_queue('test.queue')

        # Bind the queue to the exchange, so the queue will get messages published to the exchange
        yield from self.queue.bind(self.exchange, 'routing.key')

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

        # RabbitMQ span
        # self.assertEqual()

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

        # RabbitMQ span
        # self.assertEqual()

    # TBD
    # def test_get_without_parent_span(self):

    def test_consume(self):
        def handle_message(msg):
            print("got the message")

        @asyncio.coroutine
        def test():
            self.queue.consume(handle_message)

            msg1 = asynqp.Message({'consume': 'this'})
            self.exchange.publish(msg1, 'routing.key')
            msg2 = asynqp.Message({'consume': 'that'})
            self.exchange.publish(msg2, 'routing.key')

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        rabbitmq_span1 = spans[0]
        rabbitmq_span2 = spans[1]
        test_span = spans[2]

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

        # RabbitMQ span
        # self.assertEqual()
