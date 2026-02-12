# (c) Copyright IBM Corp. 2025


import os
import threading
import time
from typing import Generator, List

import pytest
from confluent_kafka import Consumer, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic
from mock import Mock, patch
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import format_span_id

from instana.configurator import config
from instana.instrumentation.kafka import confluent_kafka_python
from instana.instrumentation.kafka.confluent_kafka_python import (
    clear_context,
    close_consumer_span,
    consumer_span,
    save_consumer_span_into_context,
    trace_kafka_close,
)
from instana.options import StandardOptions
from instana.singletons import agent, get_tracer
from instana.span.span import InstanaSpan
from instana.util.config import parse_filtered_endpoints_from_yaml
from tests.helpers import get_first_span_by_filter, testenv


class TestConfluentKafka:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
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

        if "tracing" in config:
            config.pop("tracing")

        for key in list(os.environ.keys()):
            if key.startswith("INSTANA_TRACING_FILTER_"):
                del os.environ[key]

    def test_trace_confluent_kafka_produce(self) -> None:
        with self.tracer.start_as_current_span("test"):
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

    def test_trace_confluent_kafka_produce_with_keyword_topic(self) -> None:
        """Test that tracing works when topic is passed as a keyword argument."""
        with self.tracer.start_as_current_span("test"):
            # Pass topic as a keyword argument
            self.producer.produce(topic=testenv["kafka_topic"], value=b"raw_bytes")
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

    def test_trace_confluent_kafka_produce_with_keyword_args(self) -> None:
        """Test that tracing works when both topic and headers are passed as keyword arguments."""
        with self.tracer.start_as_current_span("test"):
            # Pass both topic and headers as keyword arguments
            self.producer.produce(
                topic=testenv["kafka_topic"],
                value=b"raw_bytes",
                headers=[("custom-header", b"header-value")],
            )
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

        with self.tracer.start_as_current_span("test"):
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

        with self.tracer.start_as_current_span("test"):
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

        with self.tracer.start_as_current_span("test"):
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

    @patch.dict(
        os.environ,
        {"INSTANA_TRACING_FILTER_EXCLUDE_KAFKA_ATTRIBUTES": "type;kafka;strict"},
    )
    def test_filter_confluent_kafka(self) -> None:
        agent.options.set_trace_configurations()
        with self.tracer.start_as_current_span("test"):
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes")
            self.producer.flush(timeout=10)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    @patch.dict(
        os.environ,
        {
            "INSTANA_TRACING_FILTER_EXCLUDE_KAFKA_PRODUCER_ATTRIBUTES": "type;kafka;strict|kafka.access;produce;strict"
        },
    )
    def test_filter_confluent_kafka_producer(self) -> None:
        agent.options.set_trace_configurations()
        with self.tracer.start_as_current_span("test-span"):
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

    @patch.dict(
        os.environ,
        {
            "INSTANA_TRACING_FILTER_EXCLUDE_KAFKA_CONSUMER_ATTRIBUTES": "type;kafka;strict|kafka.access;consume;strict"
        },
    )
    def test_filter_confluent_kafka_consumer(self) -> None:
        agent.options.set_trace_configurations()
        # Produce some events
        self.producer.produce(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.produce(testenv["kafka_topic"], b"raw_bytes2")
        self.producer.flush()

        with self.tracer.start_as_current_span("test-span"):
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
            "INSTANA_TRACING_FILTER_EXCLUDE_KAFKA_ATTRIBUTES": "kafka.access;consume,send,produce;contains|kafka.service;span-topic,topic1,topic2;strict|kafka.access;*;strict",
        },
    )
    def test_filter_confluent_specific_topic(self) -> None:
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

        with self.tracer.start_as_current_span("test-span"):
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

    def test_filter_confluent_specific_topic_with_config_file(self) -> None:
        agent.options.span_filters = parse_filtered_endpoints_from_yaml(
            "tests/util/test_configuration-1.yaml"
        )

        with self.tracer.start_as_current_span("test-span"):
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
        self.producer.produce(f"{testenv['kafka_topic']}-wo-tc", b"raw_bytes1")
        self.producer.flush()

        # Consume the events
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "my-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([f"{testenv['kafka_topic']}-wo-tc"])

        msg = consumer.poll(timeout=30)  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        producer_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "produce"
            and span.data["kafka"]["service"] == f"{testenv['kafka_topic']}-wo-tc",
        )

        poll_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "poll"
            and span.data["kafka"]["service"] == f"{testenv['kafka_topic']}-wo-tc",
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
        config["tracing"]["filter"] = {
            "exclude": [
                {
                    "name": "Kafka",
                    "attributes": [
                        {
                            "key": "kafka.service",
                            "values": [f"{testenv['kafka_topic']}_1"],
                        },
                        {"key": "kafka.access", "values": ["produce"]},
                    ],
                    "suppression": True,
                },
                {
                    "name": "Kafka",
                    "attributes": [
                        {
                            "key": "kafka.service",
                            "values": [f"{testenv['kafka_topic']}_2"],
                        },
                        {"key": "kafka.access", "values": ["consume"]},
                    ],
                    "suppression": True,
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
        assert confluent_kafka_python.consumer_token.get(None) is None

        # Save span into context
        save_consumer_span_into_context(span)

        # Verify token is stored
        assert confluent_kafka_python.consumer_token.get(None) is not None

    def test_close_consumer_span_recording_span(self, span: "InstanaSpan") -> None:
        """Test close_consumer_span with a recording span."""
        # Save span into context first
        save_consumer_span_into_context(span)
        assert confluent_kafka_python.consumer_token.get(None) is not None

        # Verify span is recording
        assert span.is_recording()

        # Close the span
        close_consumer_span(span)

        # Verify span was ended and context cleared
        assert not span.is_recording()
        assert consumer_span.get(None) is None
        assert confluent_kafka_python.consumer_token.get(None) is None

    def test_clear_context(self, span: "InstanaSpan") -> None:
        """Test clear_context function."""
        # Save span into context
        save_consumer_span_into_context(span)

        # Verify context has data
        assert consumer_span.get(None) == span
        assert confluent_kafka_python.consumer_token.get(None) is not None

        # Clear context
        clear_context()

        # Verify all context is cleared
        assert consumer_span.get(None) is None
        assert confluent_kafka_python.consumer_token.get(None) is None

    def test_trace_kafka_close_exception_handling(self, span: "InstanaSpan") -> None:
        """Test trace_kafka_close handles exceptions and still cleans up spans."""
        # Save span into context
        save_consumer_span_into_context(span)

        # Verify span is in context
        assert consumer_span.get(None) == span
        assert confluent_kafka_python.consumer_token.get(None) is not None

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
        assert confluent_kafka_python.consumer_token.get(None) is None

        # Verify span was ended
        assert not span.is_recording()

    def test_confluent_kafka_poll_returns_none(self) -> None:
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "test-empty-poll-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([testenv["kafka_topic"] + "_3"])

        # Consume any existing messages to ensure topic is empty
        while True:
            msg = consumer.poll(timeout=0.5)
            if msg is None:
                break

        with self.tracer.start_as_current_span("test"):
            msg = consumer.poll(timeout=0.1)

            assert msg is None

        consumer.close()

        spans = self.recorder.queued_spans()

        assert len(spans) == 1
        test_span = spans[0]
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_confluent_kafka_poll_returns_none_with_context_cleanup(self) -> None:
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "test-context-cleanup-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([testenv["kafka_topic"] + "_3"])

        # Consume any existing messages to ensure topic is empty
        while True:
            msg = consumer.poll(timeout=0.5)
            if msg is None:
                break

        # Clear any spans created during cleanup
        self.recorder.clear_spans()

        with self.tracer.start_as_current_span("test"):
            for _ in range(3):
                msg = consumer.poll(timeout=0.1)
                if msg is not None:
                    print(f"DEBUG: Unexpected message: {msg.value()}")
                assert msg is None

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        test_span = spans[0]
        assert test_span.n == "sdk"

    def test_confluent_kafka_poll_none_then_message(self) -> None:
        # First, create a temporary consumer to clean up any existing messages
        cleanup_config = self.kafka_config.copy()
        cleanup_config["group.id"] = "test-none-then-message-cleanup"
        cleanup_config["auto.offset.reset"] = "earliest"

        cleanup_consumer = Consumer(cleanup_config)
        cleanup_consumer.subscribe([testenv["kafka_topic"] + "_3"])

        # Consume any existing messages
        while True:
            msg = cleanup_consumer.poll(timeout=0.5)
            if msg is None:
                break

        cleanup_consumer.close()

        # Clear any spans created during cleanup
        self.recorder.clear_spans()

        # Now run the actual test with a fresh consumer
        consumer_config = self.kafka_config.copy()
        consumer_config["group.id"] = "test-none-then-message-group"
        consumer_config["auto.offset.reset"] = "earliest"

        consumer = Consumer(consumer_config)
        consumer.subscribe([testenv["kafka_topic"] + "_3"])

        with self.tracer.start_as_current_span("test"):
            msg1 = consumer.poll(timeout=0.1)
            assert msg1 is None

            self.producer.produce(testenv["kafka_topic"] + "_3", b"test_message")
            self.producer.flush(timeout=10)

            msg2 = consumer.poll(timeout=5)
            assert msg2 is not None
            assert msg2.value() == b"test_message"

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        kafka_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka" and span.data["kafka"]["access"] == "poll",
        )
        assert kafka_span is not None
        assert kafka_span.data["kafka"]["service"] == testenv["kafka_topic"] + "_3"

        kafka_span = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "produce",
        )
        assert kafka_span is not None
        assert kafka_span.data["kafka"]["service"] == testenv["kafka_topic"] + "_3"

    def test_confluent_kafka_poll_multithreaded_context_isolation(self) -> None:
        agent.options.allow_exit_as_root = True
        agent.options.set_trace_configurations()

        # Produce messages to multiple topics
        num_threads = 3
        messages_per_topic = 2

        for i in range(num_threads):
            topic = f"{testenv['kafka_topic']}_thread_{i}"
            # Create topic
            try:
                self.kafka_client.create_topics(
                    [NewTopic(topic, num_partitions=1, replication_factor=1)]
                )
            except KafkaException:
                pass

            # Produce messages
            for j in range(messages_per_topic):
                self.producer.produce(topic, f"message_{j}".encode())

        self.producer.flush(timeout=10)
        time.sleep(1)  # Allow messages to be available

        # Track results from each thread
        thread_results: List[dict] = []
        thread_errors: List[Exception] = []
        lock = threading.Lock()

        def consume_from_topic(thread_id: int) -> None:
            try:
                topic = f"{testenv['kafka_topic']}_thread_{thread_id}"
                consumer_config = self.kafka_config.copy()
                consumer_config["group.id"] = f"test-multithread-group-{thread_id}"
                consumer_config["auto.offset.reset"] = "earliest"

                consumer = Consumer(consumer_config)
                consumer.subscribe([topic])

                messages_consumed = 0
                none_polls = 0
                max_polls = 10

                with self.tracer.start_as_current_span(f"thread-{thread_id}"):
                    for _ in range(max_polls):
                        msg = consumer.poll(timeout=1.0)

                        if msg is None:
                            none_polls += 1
                            _ = consumer_span.get(None)
                        else:
                            if msg.error():
                                continue
                            messages_consumed += 1

                            assert msg.topic() == topic

                            if messages_consumed >= messages_per_topic:
                                break

                consumer.close()

                with lock:
                    thread_results.append(
                        {
                            "thread_id": thread_id,
                            "topic": topic,
                            "messages_consumed": messages_consumed,
                            "none_polls": none_polls,
                            "success": True,
                        }
                    )

            except Exception as e:
                with lock:
                    thread_errors.append(e)
                    thread_results.append(
                        {"thread_id": thread_id, "success": False, "error": str(e)}
                    )

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=consume_from_topic, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=30)

        assert len(thread_errors) == 0, f"Errors in threads: {thread_errors}"

        assert len(thread_results) == num_threads
        for result in thread_results:
            assert result[
                "success"
            ], f"Thread {result['thread_id']} failed: {result.get('error')}"
            assert (
                result["messages_consumed"] == messages_per_topic
            ), f"Thread {result['thread_id']} consumed {result['messages_consumed']} messages, expected {messages_per_topic}"

        spans = self.recorder.queued_spans()

        expected_min_spans = num_threads * (1 + messages_per_topic * 2)
        assert (
            len(spans) >= expected_min_spans
        ), f"Expected at least {expected_min_spans} spans, got {len(spans)}"

        for i in range(num_threads):
            topic = f"{testenv['kafka_topic']}_thread_{i}"

            poll_spans = [
                s
                for s in spans
                if s.n == "kafka"
                and s.data.get("kafka", {}).get("access") == "poll"
                and s.data.get("kafka", {}).get("service") == topic
            ]

            assert (
                len(poll_spans) >= 1
            ), f"Expected poll spans for topic {topic}, got {len(poll_spans)}"

        topics_to_delete = [
            f"{testenv['kafka_topic']}_thread_{i}" for i in range(num_threads)
        ]
        self.kafka_client.delete_topics(topics_to_delete)
        time.sleep(1)

    def test_confluent_kafka_poll_multithreaded_with_none_returns(self) -> None:
        num_threads = 5

        thread_errors: List[Exception] = []
        lock = threading.Lock()

        def poll_empty_topic(thread_id: int) -> None:
            try:
                consumer_config = self.kafka_config.copy()
                consumer_config["group.id"] = f"test-empty-poll-{thread_id}"
                consumer_config["auto.offset.reset"] = "earliest"

                consumer = Consumer(consumer_config)
                consumer.subscribe([testenv["kafka_topic"] + "_3"])

                # Consume any existing messages to ensure topic is empty
                while True:
                    msg = consumer.poll(timeout=0.5)
                    if msg is None:
                        break

                with self.tracer.start_as_current_span(
                    f"empty-poll-thread-{thread_id}"
                ):
                    for _ in range(5):
                        msg = consumer.poll(timeout=0.1)
                        assert msg is None, "Expected None from empty topic"

                        time.sleep(0.01)

                consumer.close()

            except Exception as e:
                with lock:
                    thread_errors.append(e)

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=poll_empty_topic, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=10)

        assert (
            len(thread_errors) == 0
        ), f"Context errors in threads: {[str(e) for e in thread_errors]}"

        spans = self.recorder.queued_spans()

        test_spans = [s for s in spans if s.n == "sdk"]
        assert (
            len(test_spans) == num_threads
        ), f"Expected {num_threads} test spans, got {len(test_spans)}"

        kafka_spans = [s for s in spans if s.n == "kafka"]
        assert (
            len(kafka_spans) == 0
        ), f"Expected no kafka spans for None polls, got {len(kafka_spans)}"

    def test_filter_confluent_kafka_by_category(self) -> None:
        os.environ["INSTANA_TRACING_FILTER_EXCLUDE_CATEGORY_ATTRIBUTES"] = (
            "category;messaging"
        )
        agent.options = StandardOptions()
        with self.tracer.start_as_current_span("test"):
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes")
            self.producer.flush(timeout=10)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    def test_filter_confluent_kafka_by_kind(self) -> None:
        os.environ["INSTANA_TRACING_FILTER_EXCLUDE_KIND_ATTRIBUTES"] = "kind;exit"
        agent.options = StandardOptions()
        with self.tracer.start_as_current_span("test"):
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes")
            self.producer.flush(timeout=10)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1
