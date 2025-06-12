import asyncio
from typing import Any, Generator

import aioamqp
import pytest

from instana.singletons import tracer
from tests.helpers import testenv
from aioamqp.properties import Properties
from aioamqp.envelope import Envelope

testenv["rabbitmq_host"] = "127.0.0.1"
testenv["rabbitmq_port"] = 5672


class TestAioamqp:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        yield
        self.loop.run_until_complete(self.delete_queue())
        if self.loop.is_running():
            self.loop.close()

    async def delete_queue(self) -> None:
        _, protocol = await aioamqp.connect(
            testenv["rabbitmq_host"],
            testenv["rabbitmq_port"],
        )
        channel = await protocol.channel()
        await channel.queue_delete("message_queue")
        await asyncio.sleep(1)

    async def publish_message(self) -> None:
        transport, protocol = await aioamqp.connect(
            testenv["rabbitmq_host"],
            testenv["rabbitmq_port"],
        )
        channel = await protocol.channel()

        await channel.queue_declare(queue_name="message_queue")

        message = "Instana test message"
        await channel.basic_publish(
            message.encode(), exchange_name="", routing_key="message_queue"
        )

        await protocol.close()
        transport.close()

    async def consume_message(self) -> None:
        async def callback(
            channel: Any,
            body: bytes,
            envelope: Envelope,
            properties: Properties,
        ) -> None:
            with tracer.start_as_current_span("callback-span"):
                await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)

        _, protocol = await aioamqp.connect(
            testenv["rabbitmq_host"], testenv["rabbitmq_port"]
        )
        channel = await protocol.channel()
        await channel.queue_declare(queue_name="message_queue")
        await channel.basic_consume(callback, queue_name="message_queue", no_ack=False)

    def test_basic_publish(self) -> None:
        with tracer.start_as_current_span("test-span"):
            self.loop.run_until_complete(self.publish_message())

        spans = self.recorder.queued_spans()

        assert len(spans) == 2
        publisher_span = spans[0]
        test_span = spans[1]

        assert publisher_span.n == "amqp"
        assert publisher_span.data["amqp"]["command"] == "publish"
        assert publisher_span.data["amqp"]["routingkey"] == "message_queue"
        assert publisher_span.data["amqp"]["connection"] == "127.0.0.1:5672"

        assert publisher_span.p == test_span.s

        assert test_span.n == "sdk"
        assert not test_span.p

    def test_basic_consumer(self) -> None:
        with tracer.start_as_current_span("test-span"):
            self.loop.run_until_complete(self.publish_message())
            self.loop.run_until_complete(self.consume_message())

        spans = self.recorder.queued_spans()

        assert len(spans) == 4

        publisher_span = spans[0]
        callback_span = spans[1]
        consumer_span = spans[2]
        test_span = spans[3]

        assert publisher_span.n == "amqp"
        assert publisher_span.data["amqp"]["command"] == "publish"
        assert publisher_span.data["amqp"]["routingkey"] == "message_queue"
        assert publisher_span.data["amqp"]["connection"] == "127.0.0.1:5672"
        assert publisher_span.p == test_span.s

        assert callback_span.n == "sdk"
        assert callback_span.data["sdk"]["name"] == "callback-span"
        assert callback_span.data["sdk"]["type"] == "intermediate"
        assert callback_span.p == consumer_span.s

        assert consumer_span.n == "amqp"
        assert consumer_span.data["amqp"]["command"] == "consume"
        assert consumer_span.data["amqp"]["routingkey"] == "message_queue"
        assert consumer_span.data["amqp"]["connection"] == "127.0.0.1:5672"
        assert (
            consumer_span.data["amqp"]["connection"]
            == publisher_span.data["amqp"]["connection"]
        )
        assert consumer_span.p == test_span.s

        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test-span"
