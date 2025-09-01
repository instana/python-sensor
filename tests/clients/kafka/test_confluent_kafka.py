# (c) Copyright IBM Corp. 2025

import os
import time
from typing import Generator

import pytest
from confluent_kafka import (
    Consumer,
    KafkaException,
    Producer,
)
from confluent_kafka.admin import AdminClient, NewTopic
from mock import patch, Mock
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import format_span_id

from instana.configurator import config
from instana.options import StandardOptions
from instana.singletons import agent, tracer
from instana.util.config import parse_ignored_endpoints_from_yaml
from tests.helpers import get_first_span_by_filter, testenv
from instana.instrumentation.kafka import confluent_kafka_python
from instana.instrumentation.kafka.confluent_kafka_python import (
    clear_context,
    save_consumer_span_into_context,
    close_consumer_span,
    trace_kafka_close,
    consumer_span,
)
from instana.span.span import InstanaSpan


class TestConfluentKafka:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # Kafka admin client
        self.kafka_config = {"bootstrap.servers": testenv["kafka_bootstrap_servers"][0]}
        self.kafka_client = AdminClient(self.kafka_config)

        try:
            _ = self.kafka_client.create_topics(  # noqa: F841
                [
                    NewTopic(
                        testenv["kafka_topic"],
                        num_partitions=1,
                        replication_factor=1,
                    ),
                    NewTopic(
                        testenv["kafka_topic"] + "_1",
                        num_partitions=1,
                        replication_factor=1,
                    ),
                    NewTopic(
                        testenv["kafka_topic"] + "_2",
                        num_partitions=1,
                        replication_factor=1,
                    ),
                    NewTopic(
                        testenv["kafka_topic"] + "_3",
                        num_partitions=1,
                        replication_factor=1,
                    ),
                ]
            )
        except KafkaException:
            pass

        # Kafka producer
        self.producer = Producer(self.kafka_config)
        agent.options = StandardOptions()
        yield
        # teardown
        # Clear spans before resetting options
        self.recorder.clear_spans()

        # Clear context
        clear_context()

        # Close connections
        self.kafka_client.delete_topics(
            [
                testenv["kafka_topic"],
                testenv["kafka_topic"] + "_1",
                testenv["kafka_topic"] + "_2",
                testenv["kafka_topic"] + "_3",
            ]
        )
        time.sleep(3)

    def test_trace_confluent_kafka_produce(self) -> None:
        with tracer.start_as_current_span("test"):
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes")
            self.producer.flush(timeout=10)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        kafka_span = spans[0]
        test_span = spans[1]

        # Same traceId
        assert test_span.t == kafka_span.t

        # Parent relationships
        assert kafka_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not kafka_span.ec

        assert kafka_span.n == "kafka"
        assert kafka_span.k == SpanKind.CLIENT
        assert kafka_span.data["kafka"]["service"] == testenv["kafka_topic"]
        assert kafka_span.data["kafka"]["access"] == "produce"

    def test_trace_confluent_kafka_consume(self) -> None:
        agent.options.set_trace_configurations()
        # Produce some events
        self.producer.produce(testenv["kafka_topic"], value=b"raw_bytes1")
        self.producer.flush(timeout=30)

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([testenv["kafka_topic"]])

        with tracer.start_as_current_span("test"):
            msgs = consumer.consume(num_messages=1, timeout=60)  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

    def test_trace_confluent_kafka_poll(self) -> None:
        # Produce some events
        self.producer.produce(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.produce(testenv["kafka_topic"], b"raw_bytes2")
        self.producer.flush()

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([testenv["kafka_topic"]])

        with tracer.start_as_current_span("test"):
            msg = consumer.poll(timeout=3)  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        def filter(span):
            return span.n == "kafka" and span.data["kafka"]["access"] == "poll"

        kafka_span = get_first_span_by_filter(spans, filter)

        def filter(span):
            return span.n == "sdk" and span.data["sdk"]["name"] == "test"

        test_span = get_first_span_by_filter(spans, filter)

        # Same traceId
        assert test_span.t == kafka_span.t

        # Parent relationships
        assert kafka_span.p == test_span.s

        assert kafka_span.n == "kafka"
        assert kafka_span.k == SpanKind.SERVER
        assert kafka_span.data["kafka"]["service"] == testenv["kafka_topic"]
        assert kafka_span.data["kafka"]["access"] == "poll"

    def test_trace_confluent_kafka_error(self) -> None:
        # Consume the events
        consumer_config = {"bootstrap.servers": ["some_inexistent_host:9094"]}
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe(["inexistent_kafka_topic"])

        with tracer.start_as_current_span("test"):
            consumer.consume(-10)

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        kafka_span = spans[0]
        test_span = spans[len(spans) - 1]

        # Same traceId
        assert test_span.t == kafka_span.t

        # Parent relationships
        assert kafka_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert kafka_span.ec == 1

        assert kafka_span.n == "kafka"
        assert kafka_span.k == SpanKind.SERVER
        assert not kafka_span.data["kafka"]["service"]
        assert kafka_span.data["kafka"]["access"] == "consume"
        assert (
            kafka_span.data["kafka"]["error"]
            == "num_messages must be between 0 and 1000000 (1M)"
        )

    @patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "kafka"})
    def test_ignore_confluent_kafka(self) -> None:
        agent.options.set_trace_configurations()
        with tracer.start_as_current_span("test"):
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes")
            self.producer.flush(timeout=10)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    @patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "kafka:produce"})
    def test_ignore_confluent_kafka_producer(self) -> None:
        agent.options.set_trace_configurations()
        with tracer.start_as_current_span("test-span"):
            # Produce some events
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes1")
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes2")
            self.producer.flush()

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([testenv["kafka_topic"]])
        consumer.consume(num_messages=2, timeout=60)

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    @patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "kafka:consume"})
    def test_ignore_confluent_kafka_consumer(self) -> None:
        agent.options.set_trace_configurations()
        # Produce some events
        self.producer.produce(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.produce(testenv["kafka_topic"], b"raw_bytes2")
        self.producer.flush()

        with tracer.start_as_current_span("test-span"):
            # Consume the events
            consumer_config = self.kafka_config.copy()
            consumer_config["group.id"] = "my-group"
            consumer_config["auto.offset.reset"] = "earliest"

            consumer = Consumer(consumer_config)
            consumer.subscribe([testenv["kafka_topic"]])
            consumer.consume(num_messages=2, timeout=60)

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

    @patch.dict(
        os.environ,
        {
            "INSTANA_IGNORE_ENDPOINTS_PATH": "tests/util/test_configuration-1.yaml",
        },
    )
    def test_ignore_confluent_specific_topic(self) -> None:
        agent.options.set_trace_configurations()
        self.kafka_client.create_topics(  # noqa: F841
            [
                NewTopic(
                    testenv["kafka_topic"] + "_1",
                    num_partitions=1,
                    replication_factor=1,
                ),
            ]
        )

        with tracer.start_as_current_span("test-span"):
            # Produce some events
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes1")
            self.producer.produce(testenv["kafka_topic"] + "_1", b"raw_bytes1")
            self.producer.flush()

            # Consume the events
            consumer_config = self.kafka_config.copy()
            consumer_config["group.id"] = "my-group"
            consumer_config["auto.offset.reset"] = "earliest"

            consumer = Consumer(consumer_config)
            consumer.subscribe([testenv["kafka_topic"], testenv["kafka_topic"] + "_1"])
            consumer.consume(num_messages=2, timeout=60)

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 3

        span_to_be_filtered = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["service"] == "span-topic",
        )
        assert span_to_be_filtered not in filtered_spans

        self.kafka_client.delete_topics(
            [
                testenv["kafka_topic"] + "_1",
            ]
        )

    def test_ignore_confluent_specific_topic_with_config_file(self) -> None:
        agent.options.ignore_endpoints = parse_ignored_endpoints_from_yaml(
            "tests/util/test_configuration-1.yaml"
        )

        with tracer.start_as_current_span("test-span"):
            # Produce some events
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes1")
            self.producer.flush()

            # Consume the events
            consumer_config = self.kafka_config.copy()
            consumer_config["group.id"] = "my-group"
            consumer_config["auto.offset.reset"] = "earliest"

            consumer = Consumer(consumer_config)
            consumer.subscribe([testenv["kafka_topic"]])
            consumer.consume(num_messages=1, timeout=60)
        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    def test_confluent_kafka_consumer_root_exit(self) -> None:
        agent.options.allow_exit_as_root = True

        self.producer.produce(testenv["kafka_topic"] + "_1", b"raw_bytes")
        self.producer.produce(testenv["kafka_topic"] + "_2", b"raw_bytes")
        self.producer.flush(timeout=10)

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe(
            [
                testenv["kafka_topic"] + "_1",
                testenv["kafka_topic"] + "_2",
            ]
        )

        consumer.consume(num_messages=2, timeout=60)  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        producer_span_1 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "produce"
            and span.data["kafka"]["service"] == "span-topic_1",
        )
        producer_span_2 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "produce"
            and span.data["kafka"]["service"] == "span-topic_2",
        )
        consumer_span_1 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "consume"
            and span.data["kafka"]["service"] == "span-topic_1",
        )
        consumer_span_2 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "consume"
            and span.data["kafka"]["service"] == "span-topic_2",
        )

        # same trace id, different span ids
        assert producer_span_1.t == consumer_span_1.t
        assert producer_span_1.s == consumer_span_1.p
        assert producer_span_1.s != consumer_span_1.s

        assert producer_span_2.t == consumer_span_2.t
        assert producer_span_2.s == consumer_span_2.p
        assert producer_span_2.s != consumer_span_2.s

        self.kafka_client.delete_topics(
            [
                testenv["kafka_topic"] + "_1",
                testenv["kafka_topic"] + "_2",
            ]
        )

    def test_confluent_kafka_poll_root_exit_with_trace_correlation(self) -> None:
        agent.options.allow_exit_as_root = True
        agent.options.set_trace_configurations()

        # Produce some events
        self.producer.produce(testenv["kafka_topic"] + "-poll", b"raw_bytes1")
        self.producer.flush()

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([testenv["kafka_topic"] + "-poll"])

        msg = consumer.poll(timeout=30)  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        producer_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "produce"
            and span.data["kafka"]["service"] == "span-topic-poll",
        )

        poll_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "poll"
            and span.data["kafka"]["service"] == "span-topic-poll",
        )

        # Same traceId
        assert producer_span.t == poll_span.t
        assert producer_span.s == poll_span.p
        assert producer_span.s != poll_span.s

    def test_confluent_kafka_poll_root_exit_without_trace_correlation(self) -> None:
        agent.options.allow_exit_as_root = True
        agent.options.kafka_trace_correlation = False

        # Produce some events
        self.producer.produce(f'{testenv["kafka_topic"]}-wo-tc', b"raw_bytes1")
        self.producer.flush()

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([f'{testenv["kafka_topic"]}-wo-tc'])

        msg = consumer.poll(timeout=30)  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        producer_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "produce"
            and span.data["kafka"]["service"] == f'{testenv["kafka_topic"]}-wo-tc',
        )

        poll_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "poll"
            and span.data["kafka"]["service"] == f'{testenv["kafka_topic"]}-wo-tc',
        )

        # Different traceId
        assert producer_span.t != poll_span.t
        assert producer_span.s != poll_span.p
        assert producer_span.s != poll_span.s

    def test_confluent_kafka_poll_root_exit_error(self) -> None:
        agent.options.allow_exit_as_root = True
        agent.options.set_trace_configurations()

        # Produce some events
        self.producer.produce(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.flush()

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([testenv["kafka_topic"]])

        msg = consumer.poll(timeout="wrong_value")  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        poll_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka" and span.data["kafka"]["access"] == "poll",
        )
        assert poll_span.data["kafka"]["error"] == "must be real number, not str"

    @patch.dict(os.environ, {"INSTANA_ALLOW_ROOT_EXIT_SPAN": "1"})
    def test_confluent_kafka_downstream_suppression(self) -> None:
        config["tracing"]["ignore_endpoints"] = {
            "kafka": [
                {"methods": ["produce"], "endpoints": [f"{testenv['kafka_topic']}_1"]},
                {
                    "methods": ["consume"],
                    "endpoints": [f"{testenv['kafka_topic']}_2"],
                },
            ]
        }
        agent.options.set_trace_configurations()

        self.kafka_client.create_topics(  # noqa: F841
            [
                NewTopic(
                    testenv["kafka_topic"] + "_1",
                    num_partitions=1,
                    replication_factor=1,
                ),
                NewTopic(
                    testenv["kafka_topic"] + "_2",
                    num_partitions=1,
                    replication_factor=1,
                ),
            ]
        )

        self.producer.produce(testenv["kafka_topic"] + "_1", b"raw_bytes1")
        self.producer.produce(testenv["kafka_topic"] + "_2", b"raw_bytes2")
        self.producer.flush(timeout=10)

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe(
            [
                testenv["kafka_topic"] + "_1",
                testenv["kafka_topic"] + "_2",
            ]
        )

        messages = consumer.consume(num_messages=2, timeout=60)  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        producer_span_1 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "produce"
            and span.data["kafka"]["service"] == "span-topic_1",
        )
        producer_span_2 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "produce"
            and span.data["kafka"]["service"] == "span-topic_2",
        )
        consumer_span_1 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "consume"
            and span.data["kafka"]["service"] == "span-topic_1",
        )
        consumer_span_2 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "consume"
            and span.data["kafka"]["service"] == "span-topic_2",
        )

        assert producer_span_1
        # consumer has been suppressed
        assert not consumer_span_1
        assert not consumer_span_2

        for message in messages:
            if message.topic() == "span-topic_1":
                assert message.headers() == [("x_instana_l_s", b"0")]
            else:
                assert message.headers() == [
                    ("x_instana_l_s", b"1"),
                    ("x_instana_t", format_span_id(producer_span_2.t).encode("utf-8")),
                    ("x_instana_s", format_span_id(producer_span_2.s).encode("utf-8")),
                ]

        self.kafka_client.delete_topics(
            [
                testenv["kafka_topic"] + "_1",
                testenv["kafka_topic"] + "_2",
            ]
        )

    def test_save_consumer_span_into_context(self, span: "InstanaSpan") -> None:
        """Test save_consumer_span_into_context function."""
        # Verify initial state
        assert consumer_span.get(None) is None
        assert confluent_kafka_python.consumer_token is None

        # Save span into context
        save_consumer_span_into_context(span)

        # Verify token is stored
        assert confluent_kafka_python.consumer_token is not None

    def test_close_consumer_span_recording_span(self, span: "InstanaSpan") -> None:
        """Test close_consumer_span with a recording span."""
        # Save span into context first
        save_consumer_span_into_context(span)
        assert confluent_kafka_python.consumer_token is not None

        # Verify span is recording
        assert span.is_recording()

        # Close the span
        close_consumer_span(span)

        # Verify span was ended and context cleared
        assert not span.is_recording()
        assert consumer_span.get(None) is None
        assert confluent_kafka_python.consumer_token is None

    def test_clear_context(self, span: "InstanaSpan") -> None:
        """Test clear_context function."""
        # Save span into context
        save_consumer_span_into_context(span)

        # Verify context has data
        assert consumer_span.get(None) == span
        assert confluent_kafka_python.consumer_token is not None

        # Clear context
        clear_context()

        # Verify all context is cleared
        assert consumer_span.get(None) is None
        assert confluent_kafka_python.consumer_token is None

    def test_trace_kafka_close_exception_handling(self, span: "InstanaSpan") -> None:
        """Test trace_kafka_close handles exceptions and still cleans up spans."""
        # Save span into context
        save_consumer_span_into_context(span)

        # Verify span is in context
        assert consumer_span.get(None) == span
        assert confluent_kafka_python.consumer_token is not None

        # Mock a wrapped function that raises an exception
        mock_wrapped = Mock(side_effect=Exception("Close operation failed"))
        mock_instance = Mock()

        # Call trace_kafka_close - it should handle the exception gracefully
        # and still clean up the span
        trace_kafka_close(mock_wrapped, mock_instance, (), {})

        # Verify the wrapped function was called
        mock_wrapped.assert_called_once_with()

        # Verify that despite the exception, the span was cleaned up
        assert consumer_span.get(None) is None
        assert confluent_kafka_python.consumer_token is None

        # Verify span was ended
        assert not span.is_recording()
