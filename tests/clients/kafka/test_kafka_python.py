# (c) Copyright IBM Corp. 2025

import os
from typing import Generator

import pytest
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from opentelemetry.trace import SpanKind

from instana.options import StandardOptions
from instana.singletons import agent, tracer
from instana.util.config import parse_ignored_endpoints_from_yaml
from tests.helpers import testenv


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

    def consume_from_topic(self, topic_name: str) -> None:
        consumer = KafkaConsumer(
            topic_name,
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=1000,
        )
        with tracer.start_as_current_span("test"):
            for msg in consumer:
                if msg is None:
                    break

        consumer.close()

    def test_ignore_kafka(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "kafka"

        agent.options = StandardOptions()

        with tracer.start_as_current_span("test"):
            self.producer.send(testenv["kafka_topic"], b"raw_bytes")
            self.producer.flush()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    def test_ignore_kafka_producer(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "kafka:send"

        agent.options = StandardOptions()

        with tracer.start_as_current_span("test-span"):
            # Produce some events
            self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
            self.producer.send(testenv["kafka_topic"], b"raw_bytes2")
            self.producer.flush()

            # Consume the events
        consumer = KafkaConsumer(
            testenv["kafka_topic"],
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=1000,
        )
        for msg in consumer:
            if msg is None:
                break

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    @pytest.mark.flaky(reruns=3)
    def test_ignore_kafka_consumer(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "kafka:consume"
        agent.options = StandardOptions()

        # Produce some events
        self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.send(testenv["kafka_topic"], b"raw_bytes2")
        self.producer.flush()

        # Consume the events
        self.consume_from_topic(testenv["kafka_topic"])

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    @pytest.mark.flaky(reruns=5)
    def test_ignore_specific_topic(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "kafka:consume"
        os.environ["INSTANA_IGNORE_ENDPOINTS_PATH"] = (
            "tests/util/test_configuration-1.yaml"
        )

        agent.options = StandardOptions()

        with tracer.start_as_current_span("test-span"):
            # Produce some events
            self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
            self.producer.flush()

            # Consume the events
            self.consume_from_topic(testenv["kafka_topic"])

        spans = self.recorder.queued_spans()
        assert len(spans) == 6

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 3

    def test_ignore_specific_topic_with_config_file(self) -> None:
        agent.options.ignore_endpoints = parse_ignored_endpoints_from_yaml(
            "tests/util/test_configuration-1.yaml"
        )

        # Produce some events
        self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.flush()

        # Consume the events
        self.consume_from_topic(testenv["kafka_topic"])

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1
