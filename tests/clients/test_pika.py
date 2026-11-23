# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


import contextlib
import threading
import time
from types import SimpleNamespace
from typing import Callable, Generator, Optional

import mock
import pika
import pika.adapters.blocking_connection
import pika.channel
import pika.spec
import pytest
from opentelemetry.trace.span import format_span_id

from instana.instrumentation import pika as pika_instrumentation
from instana.singletons import agent, get_tracer
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
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
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


@pytest.mark.parametrize(
    "instance, expected",
    [
        ("pika_channel", "pika_channel"),
        ("thread_safe_channel", "pika_channel"),
    ],
)
def test_get_pika_channel_resolves_pika_channel(instance, expected) -> None:
    pika_channel = pika.channel.Channel(mock.Mock(), 1, mock.Mock())
    channels = {
        "pika_channel": pika_channel,
        "thread_safe_channel": SimpleNamespace(_channel=pika_channel),
    }

    result = pika_instrumentation._get_pika_channel(channels[instance])

    assert result is channels[expected]


@pytest.mark.parametrize(
    "instance",
    [
        SimpleNamespace(connection=SimpleNamespace(_impl="connection")),
        SimpleNamespace(_channel=SimpleNamespace(connection="connection")),
    ],
    ids=["blocking_channel", "thread_safe_channel"],
)
def test_get_consumer_connection_resolves_pika_connection(instance) -> None:
    assert pika_instrumentation._get_consumer_connection(instance) == "connection"


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

    @pytest.fixture
    def sent_message(self, mocker) -> Callable[[], tuple[object, tuple[object, bytes]]]:
        """Returns the (method, (properties, body)) that was handed over to pika."""
        if hasattr(pika.channel.Channel, "_marshal_publish"):
            # pika >= 1.5.0 marshals the message on the connection
            publish = self.connection._marshal_message

            def _sent_message() -> tuple[object, tuple[object, bytes]]:
                publish.assert_called_once()
                return publish.call_args.args[1:]

        else:
            publish = mocker.patch("pika.channel.Channel._send_method")

            def _sent_message() -> tuple[object, tuple[object, bytes]]:
                publish.assert_called_once()
                return publish.call_args.args

        return _sent_message

    @mock.patch("pika.spec.Basic.Publish")
    def test_basic_publish(self, _unused, sent_message) -> None:
        self.obj._set_state(self.obj.OPEN)

        with self.tracer.start_as_current_span("testing"):
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

        assert sent_message() == (
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
    def test_basic_publish_as_root_exit_span(self, _unused, sent_message) -> None:
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

        assert sent_message() == (
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
    def test_basic_publish_with_headers(self, _unused, sent_message) -> None:
        self.obj._set_state(self.obj.OPEN)

        with self.tracer.start_as_current_span("testing"):
            self.obj.basic_publish(
                "test.exchange",
                "test.queue",
                "Hello!",
                pika.BasicProperties(headers={"X-Custom-1": "test"}),
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        rabbitmq_span = spans[0]

        assert sent_message() == (
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
    def test_basic_publish_tracing_off(self, _unused, mocker) -> None:
        mocker.patch(
            "instana.instrumentation.pika.get_tracer_tuple",
            return_value=(None, None, None),
        )

        self.obj._set_state(self.obj.OPEN)

        with self.tracer.start_as_current_span("testing"):
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

    @mock.patch("pika.spec.Basic.Consume")
    def test_basic_consume_with_consume_ok_callback(self, _unused) -> None:
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        properties = pika.BasicProperties()

        method_frame = pika.frame.Method(
            1, pika.spec.Basic.Deliver(consumer_tag="test")
        )
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()
        consume_ok_cb = mock.Mock()

        with mock.patch.object(pika.channel.Channel, "_rpc") as rpc:
            self.obj.basic_consume(
                queue="test.queue",
                on_message_callback=cb,
                consumer_tag="test",
                callback=consume_ok_cb,
            )

        # The Basic.ConsumeOk callback is left untouched
        assert rpc.call_args.args[1] == consume_ok_cb

        self.obj._on_deliver(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "consume"
        assert rabbitmq_span.data["rabbitmq"]["queue"] == "test.queue"

        cb.assert_called_once_with(self.obj, method_frame.method, properties, body)
        consume_ok_cb.assert_not_called()

    @mock.patch("pika.spec.Basic.Get")
    def test_basic_get_with_empty_queue_name(self, _unused) -> None:
        self.obj._set_state(self.obj.OPEN)

        body = "Hello!"
        properties = pika.BasicProperties()

        method_frame = pika.frame.Method(1, pika.spec.Basic.GetOk)
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        self.obj.basic_get(queue="", callback=cb)
        self.obj._on_getok(method_frame, header_frame, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        assert spans[0].data["rabbitmq"]["sort"] == "consume"

        cb.assert_called_once_with(self.obj, pika.spec.Basic.GetOk, properties, body)


class TestPikaThreadSafeChannel(_TestPika):
    def _create_obj(self) -> object:
        thread_safe_connection = pytest.importorskip(
            "pika.adapters.thread_safe_connection"
        )

        self.impl = pika.channel.Channel(self.connection, 1, self._on_openok_callback)
        self.impl._set_state(self.impl.OPEN)

        wrapper = mock.MagicMock()
        wrapper._closed_reason = None
        wrapper._connection._error = None

        channel = thread_safe_connection.Channel(self.impl, wrapper)
        # Run the consumer callbacks synchronously instead of on a worker thread
        channel._consumer_work_pool.submit = lambda fn, *args: fn(*args)
        return channel

    def test_basic_publish(self) -> None:
        with self.tracer.start_as_current_span("testing"):
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

        # Context propagation
        marshal_publish_args = self.connection._marshal_message.call_args.args
        properties, body = marshal_publish_args[2]
        assert body == b"Hello!"
        assert properties.headers == {
            "X-INSTANA-T": format_span_id(rabbitmq_span.t),
            "X-INSTANA-S": format_span_id(rabbitmq_span.s),
            "X-INSTANA-L": "1",
            "Server-Timing": f"intid;desc={hex_id(rabbitmq_span.t)}",
        }

    @mock.patch("pika.spec.Basic.Consume")
    def test_basic_consume(self, _unused) -> None:
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

        with mock.patch.object(type(self.obj), "_blocking_rpc") as blocking_rpc:
            blocking_rpc.return_value.method.consumer_tag = "test"
            self.obj.basic_consume("test.queue", cb, consumer_tag="test")

        # Register the consumer on the pika channel, like the IOLoop thread would
        send = blocking_rpc.call_args.args[1]
        send(mock.Mock())

        self.impl._on_deliver(method_frame, header_frame, body)

        # A single span covers the callback running on the worker thread
        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        rabbitmq_span = spans[0]

        # Trace context propagation
        assert rabbitmq_span.t == int(instana_headers["X-INSTANA-T"])
        assert rabbitmq_span.p == int(instana_headers["X-INSTANA-S"])

        # Error logging
        assert not rabbitmq_span.ec

        # Span tags
        assert rabbitmq_span.data["rabbitmq"]["sort"] == "consume"
        assert rabbitmq_span.data["rabbitmq"]["address"]
        assert rabbitmq_span.data["rabbitmq"]["queue"] == "test.queue"

        cb.assert_called_once_with(self.obj, method_frame.method, properties, body)

    def test_init_removes_pika_channel_consume_wrapper(self) -> None:
        # The consumer callback is traced by the thread-safe channel only
        assert not hasattr(self.impl.basic_consume, "__wrapped__")

        # Other pika channels keep their wrapper
        other_channel = pika.channel.Channel(self.connection, 2, mock.Mock())
        assert hasattr(other_channel.basic_consume, "__wrapped__")

    def test_basic_publish_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True

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
        assert rabbitmq_span.data["rabbitmq"]["key"] == "test.queue"

    def test_basic_publish_with_headers(self) -> None:
        with self.tracer.start_as_current_span("testing"):
            self.obj.basic_publish(
                "test.exchange",
                "test.queue",
                "Hello!",
                pika.BasicProperties(headers={"X-Custom-1": "test"}),
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        rabbitmq_span = spans[0]

        properties, _ = self.connection._marshal_message.call_args.args[2]
        assert properties.headers == {
            "X-Custom-1": "test",
            "X-INSTANA-T": format_span_id(rabbitmq_span.t),
            "X-INSTANA-S": format_span_id(rabbitmq_span.s),
            "X-INSTANA-L": "1",
            "Server-Timing": f"intid;desc={hex_id(rabbitmq_span.t)}",
        }

    def test_basic_publish_tracing_off(self, mocker) -> None:
        mocker.patch(
            "instana.instrumentation.pika.get_tracer_tuple",
            return_value=(None, None, None),
        )

        with self.tracer.start_as_current_span("testing"):
            self.obj.basic_publish("test.exchange", "test.queue", "Hello!")

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        # Span names are not "rabbitmq"
        for span in spans:
            assert span.n != "rabbitmq"

        # The message is published without trace context
        properties, body = self.connection._marshal_message.call_args.args[2]
        assert properties.headers is None
        assert body == b"Hello!"

    def test_basic_publish_with_publisher_attributes_error(self, mocker) -> None:
        mocker.patch(
            "instana.instrumentation.pika._extract_publisher_attributes",
            side_effect=Exception("test-error"),
        )

        with self.tracer.start_as_current_span("testing"):
            self.obj.basic_publish("test.exchange", "test.queue", "Hello!")

        # The message is still published and traced
        self.connection._marshal_message.assert_called_once()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        assert spans[0].n == "rabbitmq"
        assert not spans[0].data["rabbitmq"]["sort"]

    def test_basic_publish_with_publish_error(self) -> None:
        self.connection._marshal_message.side_effect = ValueError("test-error")

        with (
            self.tracer.start_as_current_span("testing"),
            contextlib.suppress(ValueError),
        ):
            self.obj.basic_publish("test.exchange", "test.queue", "Hello!")

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        rabbitmq_span = spans[0]
        assert rabbitmq_span.n == "rabbitmq"
        assert rabbitmq_span.ec == 1

    @mock.patch("pika.spec.Basic.Consume")
    def test_basic_consume_with_callback_error(self, _unused) -> None:
        body = "Hello!"
        properties = pika.BasicProperties()

        method_frame = pika.frame.Method(
            1, pika.spec.Basic.Deliver(consumer_tag="test")
        )
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock(side_effect=ValueError("test-error"))

        with mock.patch.object(type(self.obj), "_blocking_rpc") as blocking_rpc:
            blocking_rpc.return_value.method.consumer_tag = "test"
            self.obj.basic_consume("test.queue", cb, consumer_tag="test")

        send = blocking_rpc.call_args.args[1]
        send(mock.Mock())

        with contextlib.suppress(ValueError):
            self.impl._on_deliver(method_frame, header_frame, body)

        cb.assert_called_once_with(self.obj, method_frame.method, properties, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        assert spans[0].ec == 1

    @mock.patch("pika.spec.Basic.Consume")
    def test_basic_consume_with_consumer_attributes_error(
        self, _unused, mocker
    ) -> None:
        mocker.patch(
            "instana.instrumentation.pika._extract_consumer_tags",
            side_effect=Exception("test-error"),
        )

        body = "Hello!"
        properties = pika.BasicProperties()

        method_frame = pika.frame.Method(
            1, pika.spec.Basic.Deliver(consumer_tag="test")
        )
        header_frame = pika.frame.Header(1, len(body), properties)

        cb = mock.Mock()

        with mock.patch.object(type(self.obj), "_blocking_rpc") as blocking_rpc:
            blocking_rpc.return_value.method.consumer_tag = "test"
            self.obj.basic_consume("test.queue", cb, consumer_tag="test")

        send = blocking_rpc.call_args.args[1]
        send(mock.Mock())

        self.impl._on_deliver(method_frame, header_frame, body)

        # The callback is still called and traced
        cb.assert_called_once_with(self.obj, method_frame.method, properties, body)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        assert not spans[0].data["rabbitmq"]["sort"]
