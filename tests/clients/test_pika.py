# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import threading
import time
from typing import Generator, Optional

import mock
import pika
import pika.adapters.blocking_connection
import pika.channel
import pika.spec
import pytest
from opentelemetry.trace.span import format_span_id

from instana.singletons import agent, tracer
from instana.util.ids import hex_id


class _TestPika:
    @staticmethod
    @mock.patch("pika.connection.Connection")
    def _create_connection(connection_class_mock=None) -> object:
        return connection_class_mock()

    def _create_obj(self) -> NotImplementedError:
        raise NotImplementedError()

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        self.connection = self._create_connection()
        self._on_openok_callback = mock.Mock()
        self.obj = self._create_obj()
        yield
        # teardown
        del self.connection
        del self._on_openok_callback
        del self.obj
        # Ensure that allow_exit_as_root has the default value
        agent.options.allow_exit_as_root = False


class TestPikaBlockingChannel(_TestPika):
    @mock.patch("pika.channel.Channel", spec=pika.channel.Channel)
    def _create_obj(
        self, channel_impl: mock.MagicMock
    ) -> pika.adapters.blocking_connection.BlockingChannel:
        self.impl = channel_impl()
        self.impl.channel_number = 1

        return pika.adapters.blocking_connection.BlockingChannel(
            self.impl, self.connection
        )

    def _generate_delivery(
        self, consumer_tag: str, properties: pika.BasicProperties, body: str
    ) -> None:
        from pika.adapters.blocking_connection import _ConsumerDeliveryEvt

        # Wait until queue consumer is initialized
        while self.obj._queue_consumer_generator is None:
            time.sleep(0.25)

        method = pika.spec.Basic.Deliver(consumer_tag=consumer_tag)
        self.obj._on_consumer_generator_event(
            _ConsumerDeliveryEvt(method, properties, body)
        )

    def test_consume(self) -> None:
        consumed_deliveries = []

        def __consume() -> None:
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
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # A new span has been started
        assert rabbitmq_span.t
        assert not rabbitmq_span.p
        assert rabbitmq_span.s

        # Error logging
        assert not rabbitmq_span.ec

        # Span tags
        assert not rabbitmq_span.data["rabbitmq"]["exchange"]
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "consume"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["queue"] == "test.queue"
        assert rabbitmq_span.stack
        assert isinstance(rabbitmq_span.stack, list)
        assert len(rabbitmq_span.stack) > 0

        assert len(consumed_deliveries) == 1

    def test_consume_with_trace_context(self) -> None:
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

        instana_headers = {
            "X-INSTANA-T": "0000000000000001",
            "X-INSTANA-S": "0000000000000002",
            "X-INSTANA-L": "1",
        }
        self._generate_delivery(
            consumer_tag,
            pika.BasicProperties(headers=instana_headers),
            "Hello!",
        )

        t.join(timeout=5.0)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # Trace context propagation
        assert rabbitmq_span.t == int(instana_headers["X-INSTANA-T"])
        assert rabbitmq_span.p == int(instana_headers["X-INSTANA-S"])

        # A new span has been started
        assert rabbitmq_span.s
        assert rabbitmq_span.p != rabbitmq_span.s

    def test_consume_with_not_GeneratorType(self, mocker) -> None:
        mocker.patch(
            "instana.instrumentation.pika.isinstance",
            return_value=False,
        )

        consumed_deliveries = []

        def __consume() -> None:
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
        assert len(spans) == 0

    def test_consume_with_any_yielded(self, mocker) -> None:
        mocker.patch(
            "instana.instrumentation.pika.any",
            return_value=False,
        )

        consumed_deliveries = []

        def __consume() -> None:
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
        assert len(spans) == 0


class TestPikaBlockingChannelBlockingConnection(_TestPika):
    @mock.patch("pika.adapters.blocking_connection.BlockingConnection", autospec=True)
    def _create_connection(self, connection: Optional[mock.MagicMock] = None) -> object:
        connection._impl = mock.create_autospec(pika.connection.Connection)
        connection._impl.params = pika.connection.Parameters()
        return connection

    @mock.patch("pika.channel.Channel", spec=pika.channel.Channel)
    def _create_obj(
        self, channel_impl: mock.MagicMock
    ) -> pika.adapters.blocking_connection.BlockingChannel:
        self.impl = channel_impl()
        self.impl.channel_number = 1

        return pika.adapters.blocking_connection.BlockingChannel(
            self.impl, self.connection
        )

    def _generate_delivery(
        self,
        method: pika.spec.Basic.Deliver,
        properties: pika.BasicProperties,
        body: str,
    ) -> None:
        from pika.adapters.blocking_connection import _ConsumerDeliveryEvt

        evt = _ConsumerDeliveryEvt(method, properties, body)
        self.obj._add_pending_event(evt)
        self.obj._dispatch_events()

    def test_basic_consume(self) -> None:
        consumer_tag = "test.consumer"

        self.impl.basic_consume.return_value = consumer_tag
        self.impl._generate_consumer_tag.return_value = consumer_tag

        cb = mock.Mock()

        self.obj.basic_consume(queue="test.queue", on_message_callback=cb)

        body = "Hello!"
        properties = pika.BasicProperties()
        method = pika.spec.Basic.Deliver(consumer_tag)
        self._generate_delivery(method, properties, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # A new span has been started
        assert rabbitmq_span.t
        assert not rabbitmq_span.p
        assert rabbitmq_span.s

        # Error logging
        assert not rabbitmq_span.ec

        # Span tags
        assert not rabbitmq_span.data["rabbitmq"]["exchange"]
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "consume"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["queue"] == "test.queue"
        assert rabbitmq_span.stack
        assert isinstance(rabbitmq_span.stack, list)
        assert len(rabbitmq_span.stack) > 0

        cb.assert_called_once_with(self.obj, method, properties, body)

    def test_basic_consume_with_trace_context(self):
        consumer_tag = "test.consumer"

        self.impl.basic_consume.return_value = consumer_tag
        self.impl._generate_consumer_tag.return_value = consumer_tag

        cb = mock.Mock()

        self.obj.basic_consume(queue="test.queue", on_message_callback=cb)

        body = "Hello!"
        instana_headers = {
            "X-INSTANA-T": "0000000000000001",
            "X-INSTANA-S": "0000000000000002",
            "X-INSTANA-L": "1",
        }
        properties = pika.BasicProperties(headers=instana_headers)
        method = pika.spec.Basic.Deliver(consumer_tag)
        self._generate_delivery(method, properties, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # Trace context propagation
        assert rabbitmq_span.t == int(instana_headers["X-INSTANA-T"])
        assert rabbitmq_span.p == int(instana_headers["X-INSTANA-S"])

        # A new span has been started
        assert rabbitmq_span.s
        assert rabbitmq_span.p != rabbitmq_span.s


class TestPikaChannel(_TestPika):
    def _create_obj(self) -> pika.channel.Channel:
        return pika.channel.Channel(self.connection, 1, self._on_openok_callback)

    @mock.patch("pika.spec.Basic.Publish")
    @mock.patch("pika.channel.Channel._send_method")
    def test_basic_publish(self, send_method, _unused) -> None:
        self.obj._set_state(self.obj.OPEN)

        with tracer.start_as_current_span("testing"):
            self.obj.basic_publish("test.exchange", "test.queue", "Hello!")

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

        # Span tags
        assert rabbitmq_span.data["rabbitmq"]["exchange"] == "test.exchange"
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "publish"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["key"] == "test.queue"
        assert rabbitmq_span.stack
        assert isinstance(rabbitmq_span.stack, list)
        assert len(rabbitmq_span.stack) > 0

        send_method.assert_called_once_with(
            pika.spec.Basic.Publish(exchange="test.exchange", routing_key="test.queue"),
            (
                pika.spec.BasicProperties(
                    headers={
                        "X-INSTANA-T": format_span_id(rabbitmq_span.t),
                        "X-INSTANA-S": format_span_id(rabbitmq_span.s),
                        "X-INSTANA-L": "1",
                        "Server-Timing": f"intid;desc={hex_id(rabbitmq_span.t)}",
                    }
                ),
                b"Hello!",
            ),
        )

    @mock.patch("pika.spec.Basic.Publish")
    @mock.patch("pika.channel.Channel._send_method")
    def test_basic_publish_as_root_exit_span(self, send_method, _unused) -> None:
        agent.options.allow_exit_as_root = True
        self.obj._set_state(self.obj.OPEN)
        self.obj.basic_publish("test.exchange", "test.queue", "Hello!")

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # Parent relationships
        assert not rabbitmq_span.p

        # Error logging
        assert not rabbitmq_span.ec

        # Span tags
        assert rabbitmq_span.data["rabbitmq"]["exchange"] == "test.exchange"
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "publish"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["key"] == "test.queue"
        assert rabbitmq_span.stack
        assert isinstance(rabbitmq_span.stack, list)
        assert len(rabbitmq_span.stack) > 0

        send_method.assert_called_once_with(
            pika.spec.Basic.Publish(exchange="test.exchange", routing_key="test.queue"),
            (
                pika.spec.BasicProperties(
                    headers={
                        "X-INSTANA-T": format_span_id(rabbitmq_span.t),
                        "X-INSTANA-S": format_span_id(rabbitmq_span.s),
                        "X-INSTANA-L": "1",
                        "Server-Timing": f"intid;desc={hex_id(rabbitmq_span.t)}",
                    }
                ),
                b"Hello!",
            ),
        )

    @mock.patch("pika.spec.Basic.Publish")
    @mock.patch("pika.channel.Channel._send_method")
    def test_basic_publish_with_headers(self, send_method, _unused) -> None:
        self.obj._set_state(self.obj.OPEN)

        with tracer.start_as_current_span("testing"):
            self.obj.basic_publish(
                "test.exchange",
                "test.queue",
                "Hello!",
                pika.BasicProperties(headers={"X-Custom-1": "test"}),
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        rabbitmq_span = spans[0]

        send_method.assert_called_once_with(
            pika.spec.Basic.Publish(exchange="test.exchange", routing_key="test.queue"),
            (
                pika.spec.BasicProperties(
                    headers={
                        "X-Custom-1": "test",
                        "X-INSTANA-T": format_span_id(rabbitmq_span.t),
                        "X-INSTANA-S": format_span_id(rabbitmq_span.s),
                        "X-INSTANA-L": "1",
                        "Server-Timing": f"intid;desc={hex_id(rabbitmq_span.t)}",
                    }
                ),
                b"Hello!",
            ),
        )

    @mock.patch("pika.spec.Basic.Publish")
    @mock.patch("pika.channel.Channel._send_method")
    def test_basic_publish_tracing_off(self, send_method, _unused, mocker) -> None:
        mocker.patch(
            "instana.instrumentation.pika.tracing_is_off",
            return_value=True,
        )

        self.obj._set_state(self.obj.OPEN)

        with tracer.start_as_current_span("testing"):
            self.obj.basic_publish("test.exchange", "test.queue", "Hello!")

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        # Span names are not "rabbitmq"
        for span in spans:
            assert span.n != "rabbitmq"

    @mock.patch("pika.spec.Basic.Get")
    def test_basic_get(self, _unused) -> None:
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        properties = pika.BasicProperties()

        method_frame = pika.frame.Method(1, pika.spec.Basic.GetOk)
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_get("test.queue", cb)
        self.obj._on_getok(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # A new span has been started
        assert rabbitmq_span.t
        assert not rabbitmq_span.p
        assert rabbitmq_span.s

        # Error logging
        assert not rabbitmq_span.ec

        # Span tags
        assert not rabbitmq_span.data["rabbitmq"]["exchange"]
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "consume"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["queue"] == "test.queue"
        assert rabbitmq_span.stack
        assert isinstance(rabbitmq_span.stack, list)
        assert len(rabbitmq_span.stack) > 0

        cb.assert_called_once_with(self.obj, pika.spec.Basic.GetOk, properties, body)

    @mock.patch("pika.spec.Basic.Get")
    def test_basic_get_with_trace_context(self, _unused) -> None:
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        instana_headers = {
            "X-INSTANA-T": "0000000000000001",
            "X-INSTANA-S": "0000000000000002",
            "X-INSTANA-L": "1",
        }
        properties = pika.BasicProperties(headers=instana_headers)

        method_frame = pika.frame.Method(1, pika.spec.Basic.GetOk)
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_get("test.queue", cb)
        self.obj._on_getok(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # Trace context propagation
        assert rabbitmq_span.t == int(instana_headers["X-INSTANA-T"])
        assert rabbitmq_span.p == int(instana_headers["X-INSTANA-S"])

        # A new span has been started
        assert rabbitmq_span.s
        assert rabbitmq_span.p != rabbitmq_span.s

    @mock.patch("pika.spec.Basic.Consume")
    def test_basic_consume(self, _unused) -> None:
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        properties = pika.BasicProperties()

        method_frame = pika.frame.Method(
            1, pika.spec.Basic.Deliver(consumer_tag="test")
        )
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_consume("test.queue", cb, consumer_tag="test")
        self.obj._on_deliver(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # A new span has been started
        assert rabbitmq_span.t
        assert not rabbitmq_span.p
        assert rabbitmq_span.s

        # Error logging
        assert not rabbitmq_span.ec

        # Span tags
        assert not rabbitmq_span.data["rabbitmq"]["exchange"]
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "consume"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["queue"] == "test.queue"
        assert rabbitmq_span.stack
        assert isinstance(rabbitmq_span.stack, list)
        assert len(rabbitmq_span.stack) > 0

        cb.assert_called_once_with(self.obj, method_frame.method, properties, body)

    @mock.patch("pika.spec.Basic.Consume")
    def test_basic_consume_with_trace_context(self, _unused) -> None:
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        instana_headers = {
            "X-INSTANA-T": "0000000000000001",
            "X-INSTANA-S": "0000000000000002",
            "X-INSTANA-L": "1",
        }
        properties = pika.BasicProperties(headers=instana_headers)

        method_frame = pika.frame.Method(
            1, pika.spec.Basic.Deliver(consumer_tag="test")
        )
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_consume(
            queue="test.queue", on_message_callback=cb, consumer_tag="test"
        )
        self.obj._on_deliver(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # Trace context propagation
        assert rabbitmq_span.t == int(instana_headers["X-INSTANA-T"])
        assert rabbitmq_span.p == int(instana_headers["X-INSTANA-S"])

        # A new span has been started
        assert rabbitmq_span.s
        assert rabbitmq_span.p != rabbitmq_span.s
