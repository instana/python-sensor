# (c) Copyright IBM Corp. 2025

import pytest
from typing import Generator, TYPE_CHECKING
import asyncio
from aio_pika import Message, connect, connect_robust

from instana.singletons import agent, tracer

if TYPE_CHECKING:
    from instana.span.readable_span import ReadableSpan


class TestAioPika:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.queue_name = "test.queue"
        yield
        # teardown
        self.loop.run_until_complete(self.delete_queue())
        if self.loop.is_running():
            self.loop.close()
        # Ensure that allow_exit_as_root has the default value
        agent.options.allow_exit_as_root = False

    async def publish_message(self) -> None:
        # Perform connection
        connection = await connect()

        async with connection:
            # Creating a channel
            channel = await connection.channel()

            # Declaring queue
            queue_name = self.queue_name
            queue = await channel.declare_queue(queue_name)

            # Declaring exchange
            exchange = await channel.declare_exchange("test.exchange")
            await queue.bind(exchange, routing_key=queue_name)

            # Sending the message
            await exchange.publish(
                Message(f"Hello {queue_name}".encode()),
                routing_key=queue_name,
            )

    async def delete_queue(self) -> None:
        connection = await connect()

        async with connection:
            channel = await connection.channel()
            await channel.queue_delete(self.queue_name)

    async def consume_message(self, connect_method) -> None:
        connection = await connect_method()

        async with connection:
            # Creating channel
            channel = await connection.channel()

            # Declaring queue
            queue = await channel.declare_queue(self.queue_name)

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        if queue.name in message.body.decode():
                            break

    def test_basic_publish(self) -> None:
        with tracer.start_as_current_span("test"):
            self.loop.run_until_complete(self.publish_message())

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        rabbitmq_span = spans[0]
        test_span = spans[1]

        # Same traceId
        assert test_span.t == rabbitmq_span.t

        # Parent relationships
        assert rabbitmq_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not rabbitmq_span.ec

        # Span attributes
        assert rabbitmq_span.data["rabbitmq"]["exchange"] == "test.exchange"
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "publish"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["key"] == "test.queue"
        assert rabbitmq_span.stack
        assert isinstance(rabbitmq_span.stack, list)
        assert len(rabbitmq_span.stack) > 0

    def test_basic_publish_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        self.loop.run_until_complete(self.publish_message())

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # Parent relationships
        assert not rabbitmq_span.p

        # Error logging
        assert not rabbitmq_span.ec

        # Span attributes
        assert rabbitmq_span.data["rabbitmq"]["exchange"] == "test.exchange"
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "publish"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["key"] == "test.queue"
        assert rabbitmq_span.stack
        assert isinstance(rabbitmq_span.stack, list)
        assert len(rabbitmq_span.stack) > 0

    @pytest.mark.parametrize(
        "connect_method",
        [connect, connect_robust],
    )
    def test_basic_consume(self, connect_method) -> None:
        with tracer.start_as_current_span("test"):
            self.loop.run_until_complete(self.publish_message())
            self.loop.run_until_complete(self.consume_message(connect_method))

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        rabbitmq_publisher_span = spans[0]
        rabbitmq_consumer_span = spans[1]
        test_span = spans[2]

        # Same traceId
        assert test_span.t == rabbitmq_publisher_span.t
        assert rabbitmq_publisher_span.t == rabbitmq_consumer_span.t

        # Parent relationships
        assert rabbitmq_publisher_span.p == test_span.s
        assert rabbitmq_consumer_span.p == rabbitmq_publisher_span.s

        # Error logging
        assert not rabbitmq_publisher_span.ec
        assert not rabbitmq_consumer_span.ec
        assert not test_span.ec

        # Span attributes
        def assert_span_info(rabbitmq_span: "ReadableSpan", sort: str) -> None:
            assert rabbitmq_span.data["rabbitmq"]["exchange"] == "test.exchange"
            assert rabbitmq_span.data["rabbitmq"]["sort"] == sort
            assert rabbitmq_span.data["rabbitmq"]["address"]
            assert rabbitmq_span.data["rabbitmq"]["key"] == "test.queue"
            assert rabbitmq_span.stack
            assert isinstance(rabbitmq_span.stack, list)
            assert len(rabbitmq_span.stack) > 0

        assert_span_info(rabbitmq_publisher_span, "publish")
        assert_span_info(rabbitmq_consumer_span, "consume")
