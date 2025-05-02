# (c) Copyright IBM Corp. 2025

from typing import Generator

import pytest
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from opentelemetry.trace import SpanKind

from instana.singletons import agent, tracer
from tests.helpers import get_first_span_by_filter, testenv


class TestKafkaPython:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # Kafka admin client
        self.kafka_client = KafkaAdminClient(
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            client_id="test_kafka_python",
        )

        try:
            self.kafka_client.create_topics(
                [
                    NewTopic(
                        name=testenv["kafka_topic"],
                        num_partitions=1,
                        replication_factor=1,
                    ),
                ]
            )
        except TopicAlreadyExistsError:
            pass

        # Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=testenv["kafka_bootstrap_servers"]
        )
        yield
        # teardown
        # Ensure that allow_exit_as_root has the default value"""
        agent.options.allow_exit_as_root = False
        # Close connections
        self.producer.close()
        self.kafka_client.delete_topics([testenv["kafka_topic"]])
        self.kafka_client.close()

    def test_trace_kafka_python_send(self) -> None:
        with tracer.start_as_current_span("test"):
            future = self.producer.send(testenv["kafka_topic"], b"raw_bytes")

        record_metadata = future.get(timeout=10)  # noqa: F841

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
        assert kafka_span.data["kafka"]["access"] == "send"

    def test_trace_kafka_python_consume(self) -> None:
        # Produce some events
        self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.send(testenv["kafka_topic"], b"raw_bytes2")
        self.producer.flush()

        # Consume the events
        consumer = KafkaConsumer(
            testenv["kafka_topic"],
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            auto_offset_reset="earliest",  # consume earliest available messages
            enable_auto_commit=False,  # do not auto-commit offsets
            consumer_timeout_ms=1000,
        )

        with tracer.start_as_current_span("test"):
            for msg in consumer:
                if msg is None:
                    break

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        kafka_span = spans[0]
        test_span = spans[len(spans) - 1]

        # Same traceId
        assert test_span.t == kafka_span.t

        # Parent relationships
        assert kafka_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not kafka_span.ec

        assert kafka_span.n == "kafka"
        assert kafka_span.k == SpanKind.SERVER
        assert kafka_span.data["kafka"]["service"] == testenv["kafka_topic"]
        assert kafka_span.data["kafka"]["access"] == "consume"

    def test_trace_kafka_python_poll(self) -> None:
        # Produce some events
        self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.send(testenv["kafka_topic"], b"raw_bytes2")
        self.producer.flush()

        # Consume the events
        consumer = KafkaConsumer(
            testenv["kafka_topic"],
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            auto_offset_reset="earliest",  # consume earliest available messages
            enable_auto_commit=False,  # do not auto-commit offsets
            consumer_timeout_ms=1000,
        )

        with tracer.start_as_current_span("test"):
            msg = consumer.poll()  # noqa: F841

        consumer.close()

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
        assert kafka_span.k == SpanKind.SERVER
        assert kafka_span.data["kafka"]["service"] == testenv["kafka_topic"]
        assert kafka_span.data["kafka"]["access"] == "poll"

    def test_trace_kafka_python_error(self) -> None:
        # Consume the events
        consumer = KafkaConsumer(
            "inexistent_kafka_topic",
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            auto_offset_reset="earliest",  # consume earliest available messages
            enable_auto_commit=False,  # do not auto-commit offsets
            consumer_timeout_ms=1000,
        )

        with tracer.start_as_current_span("test"):
            for msg in consumer:
                if msg is None:
                    break

        consumer.close()

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
        assert kafka_span.ec == 1

        assert kafka_span.n == "kafka"
        assert kafka_span.k == SpanKind.SERVER
        assert kafka_span.data["kafka"]["service"] == "inexistent_kafka_topic"
        assert kafka_span.data["kafka"]["access"] == "consume"
        assert kafka_span.data["kafka"]["error"] == "StopIteration()"

    def test_kafka_consumer_root_exit(self) -> None:
        agent.options.allow_exit_as_root = True

        self.producer.send(testenv["kafka_topic"], b"raw_bytes")
        self.producer.flush()

        # Consume the events
        consumer = KafkaConsumer(
            testenv["kafka_topic"],
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            auto_offset_reset="earliest",  # consume earliest available messages
            enable_auto_commit=False,  # do not auto-commit offsets
            consumer_timeout_ms=1000,
        )

        for msg in consumer:
            if msg is None:
                break

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        producer_span = spans[0]
        consumer_span = spans[1]

        assert producer_span.s
        assert producer_span.n == "kafka"
        assert producer_span.data["kafka"]["access"] == "send"
        assert producer_span.data["kafka"]["service"] == "span-topic"

        assert consumer_span.s
        assert consumer_span.n == "kafka"
        assert consumer_span.data["kafka"]["access"] == "consume"
        assert consumer_span.data["kafka"]["service"] == "span-topic"

        assert producer_span.t == consumer_span.t

    def test_kafka_poll_root_exit(self) -> None:
        agent.options.allow_exit_as_root = True

        self.kafka_client.create_topics(
            [
                NewTopic(
                    name=testenv["kafka_topic"] + "_1",
                    num_partitions=1,
                    replication_factor=1,
                ),
                NewTopic(
                    name=testenv["kafka_topic"] + "_2",
                    num_partitions=1,
                    replication_factor=1,
                ),
                NewTopic(
                    name=testenv["kafka_topic"] + "_3",
                    num_partitions=1,
                    replication_factor=1,
                ),
            ]
        )

        self.producer.send(testenv["kafka_topic"] + "_1", b"raw_bytes1")
        self.producer.send(testenv["kafka_topic"] + "_2", b"raw_bytes2")
        self.producer.send(testenv["kafka_topic"] + "_3", b"raw_bytes3")
        self.producer.flush()

        # Consume the events
        consumer = KafkaConsumer(
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            auto_offset_reset="earliest",  # consume earliest available messages
            enable_auto_commit=False,  # do not auto-commit offsets
            consumer_timeout_ms=1000,
        )
        topics = [
            testenv["kafka_topic"] + "_1",
            testenv["kafka_topic"] + "_2",
            testenv["kafka_topic"] + "_3",
        ]
        consumer.subscribe(topics)

        messages = consumer.poll(timeout_ms=1000)  # noqa: F841
        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 6

        producer_span_1 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "send"
            and span.data["kafka"]["service"] == "span-topic_1",
        )
        producer_span_2 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "send"
            and span.data["kafka"]["service"] == "span-topic_2",
        )
        producer_span_3 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "send"
            and span.data["kafka"]["service"] == "span-topic_3",
        )

        poll_span_1 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "poll"
            and span.data["kafka"]["service"] == "span-topic_1",
        )
        poll_span_2 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "poll"
            and span.data["kafka"]["service"] == "span-topic_2",
        )
        poll_span_3 = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["access"] == "poll"
            and span.data["kafka"]["service"] == "span-topic_3",
        )

        assert producer_span_1.n == "kafka"
        assert producer_span_1.data["kafka"]["access"] == "send"
        assert producer_span_1.data["kafka"]["service"] == "span-topic_1"

        assert producer_span_2.n == "kafka"
        assert producer_span_2.data["kafka"]["access"] == "send"
        assert producer_span_2.data["kafka"]["service"] == "span-topic_2"

        assert producer_span_3.n == "kafka"
        assert producer_span_3.data["kafka"]["access"] == "send"
        assert producer_span_3.data["kafka"]["service"] == "span-topic_3"

        assert poll_span_1.n == "kafka"
        assert poll_span_1.data["kafka"]["access"] == "poll"
        assert poll_span_1.data["kafka"]["service"] == "span-topic_1"

        assert poll_span_2.n == "kafka"
        assert poll_span_2.data["kafka"]["access"] == "poll"
        assert poll_span_2.data["kafka"]["service"] == "span-topic_2"

        assert poll_span_3.n == "kafka"
        assert poll_span_3.data["kafka"]["access"] == "poll"
        assert poll_span_3.data["kafka"]["service"] == "span-topic_3"

        # same trace id, different span ids
        assert producer_span_1.t == poll_span_1.t
        assert producer_span_1.s != poll_span_1.s

        assert producer_span_2.t == poll_span_2.t
        assert producer_span_2.s != poll_span_2.s

        assert producer_span_3.t == poll_span_3.t
        assert producer_span_3.s != poll_span_3.s

        self.kafka_client.delete_topics(
            [
                testenv["kafka_topic"] + "_1",
                testenv["kafka_topic"] + "_2",
                testenv["kafka_topic"] + "_3",
            ]
        )
