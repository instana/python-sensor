# (c) Copyright IBM Corp. 2025

import os
from typing import Generator

import pytest
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from mock import patch
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import format_span_id

from instana.configurator import config
from instana.instrumentation.kafka import kafka_python
from instana.instrumentation.kafka.kafka_python import (
    clear_context,
    close_consumer_span,
    consumer_span,
    save_consumer_span_into_context,
)
from instana.options import StandardOptions
from instana.singletons import agent, tracer
from instana.span.span import InstanaSpan
from instana.util.config import parse_ignored_endpoints_from_yaml
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
        except TopicAlreadyExistsError:
            pass

        # Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=testenv["kafka_bootstrap_servers"]
        )
        agent.options = StandardOptions()
        yield
        # teardown
        # Ensure that allow_exit_as_root has the default value"""
        agent.options.allow_exit_as_root = False
        # Close connections
        self.producer.close()

        # Clear context
        clear_context()

        self.kafka_client.delete_topics(
            [
                testenv["kafka_topic"],
                testenv["kafka_topic"] + "_1",
                testenv["kafka_topic"] + "_2",
                testenv["kafka_topic"] + "_3",
            ]
        )
        self.kafka_client.close()

    def test_trace_kafka_python_send(self) -> None:
        with tracer.start_as_current_span("test"):
            future = self.producer.send(testenv["kafka_topic"], b"raw_bytes")

        _ = future.get(timeout=10)  # noqa: F841

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

    def test_trace_kafka_python_send_with_keyword_topic(self) -> None:
        """Test that tracing works when topic is passed as a keyword argument."""
        with tracer.start_as_current_span("test"):
            # Pass topic as a keyword argument
            future = self.producer.send(
                topic=testenv["kafka_topic"], value=b"raw_bytes"
            )

        _ = future.get(timeout=10)  # noqa: F841

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

    def test_trace_kafka_python_send_with_keyword_args(self) -> None:
        """Test that tracing works when both topic and headers are passed as keyword arguments."""
        with tracer.start_as_current_span("test"):
            # Pass both topic and headers as keyword arguments
            future = self.producer.send(
                topic=testenv["kafka_topic"],
                value=b"raw_bytes",
                headers=[("custom-header", b"header-value")],
            )

        _ = future.get(timeout=10)  # noqa: F841

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
        assert len(spans) == 3

        def filter(span):
            return span.n == "kafka" and span.data["kafka"]["access"] == "consume"

        kafka_span = get_first_span_by_filter(spans, filter)

        def filter(span):
            return span.n == "sdk" and span.data["sdk"]["name"] == "test"

        test_span = get_first_span_by_filter(spans, filter)

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
            msg = consumer.poll(timeout_ms=3000)  # noqa: F841

        consumer.close()

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

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

        # Error logging
        assert not test_span.ec
        assert not kafka_span.ec

        assert kafka_span.n == "kafka"
        assert kafka_span.k == SpanKind.SERVER
        assert kafka_span.data["kafka"]["service"] == testenv["kafka_topic"]
        assert kafka_span.data["kafka"]["access"] == "poll"

    def test_trace_kafka_python_error(self) -> None:
        consumer = KafkaConsumer(
            "inexistent_kafka_topic",
            bootstrap_servers=testenv["kafka_bootstrap_servers"],
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=1000,
        )

        with tracer.start_as_current_span("test"):
            consumer._client = None

            try:
                for msg in consumer:
                    if msg is None:
                        break
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        def filter(span):
            return span.n == "kafka" and span.data["kafka"]["access"] == "consume"

        kafka_span = get_first_span_by_filter(spans, filter)

        def filter(span):
            return span.n == "sdk" and span.data["sdk"]["name"] == "test"

        test_span = get_first_span_by_filter(spans, filter)

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
        assert (
            kafka_span.data["kafka"]["error"]
            == "'NoneType' object has no attribute 'poll'"
        )

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

    @patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "kafka"})
    def test_ignore_kafka(self) -> None:
        agent.options.set_trace_configurations()
        with tracer.start_as_current_span("test"):
            self.producer.send(testenv["kafka_topic"], b"raw_bytes")
            self.producer.flush()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    @patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "kafka:send"})
    def test_ignore_kafka_producer(self) -> None:
        agent.options.set_trace_configurations()
        with tracer.start_as_current_span("test-span"):
            # Produce some events
            self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
            self.producer.send(testenv["kafka_topic"], b"raw_bytes2")
            self.producer.flush()

        # Consume the events manually
        # consume_from_topic not used due to to not create sdk span
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

    @patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "kafka:consume"})
    def test_ignore_kafka_consumer(self) -> None:
        agent.options.set_trace_configurations()
        # Produce some events
        self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
        self.producer.send(testenv["kafka_topic"], b"raw_bytes2")
        self.producer.flush()

        # Consume the events
        self.consume_from_topic(testenv["kafka_topic"])

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

    @patch.dict(
        os.environ,
        {
            "INSTANA_IGNORE_ENDPOINTS_PATH": "tests/util/test_configuration-1.yaml",
        },
    )
    def test_ignore_specific_topic(self) -> None:
        agent.options.set_trace_configurations()
        with tracer.start_as_current_span("test-span"):
            # Produce some events
            self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
            self.producer.send(testenv["kafka_topic"] + "_1", b"raw_bytes1")
            self.producer.flush()

            # Consume the events
            self.consume_from_topic(testenv["kafka_topic"])
            self.consume_from_topic(testenv["kafka_topic"] + "_1")

        spans = self.recorder.queued_spans()
        assert len(spans) == 7

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 6

        span_to_be_filtered = get_first_span_by_filter(
            spans,
            lambda span: span.n == "kafka"
            and span.data["kafka"]["service"] == "span-topic",
        )
        assert span_to_be_filtered not in filtered_spans

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
        assert len(spans) == 1

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
        assert len(spans) == 3

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

    def test_kafka_poll_root_exit_with_trace_correlation(self) -> None:
        agent.options.allow_exit_as_root = True

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

    def test_kafka_poll_root_exit_without_trace_correlation(self) -> None:
        agent.options.allow_exit_as_root = True
        agent.options.kafka_trace_correlation = False

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

        # different trace id and span ids
        assert producer_span_1.t != poll_span_1.t
        assert producer_span_1.s != poll_span_1.s

        assert producer_span_2.t != poll_span_2.t
        assert producer_span_2.s != poll_span_2.s

        assert producer_span_3.t != poll_span_3.t
        assert producer_span_3.s != poll_span_3.s

        for topic_partition, partition_messages in messages.items():
            for message in partition_messages:
                assert not message.headers

    @patch.dict(os.environ, {"INSTANA_ALLOW_ROOT_EXIT_SPAN": "1"})
    def test_kafka_downstream_suppression(self) -> None:
        config["tracing"]["ignore_endpoints"] = {
            "kafka": [
                {"methods": ["send"], "endpoints": [f"{testenv['kafka_topic']}_1"]},
                {
                    "methods": ["consume"],
                    "endpoints": [f"{testenv['kafka_topic']}_2"],
                },
            ]
        }
        agent.options.set_trace_configurations()

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
        assert len(spans) == 5

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

        assert poll_span_2.n == "kafka"
        assert poll_span_2.data["kafka"]["access"] == "poll"
        assert poll_span_2.data["kafka"]["service"] == "span-topic_2"

        assert poll_span_3.n == "kafka"
        assert poll_span_3.data["kafka"]["access"] == "poll"
        assert poll_span_3.data["kafka"]["service"] == "span-topic_3"

        # same trace id, different span ids
        assert producer_span_2.t == poll_span_2.t
        assert producer_span_2.s != poll_span_2.s

        assert producer_span_3.t == poll_span_3.t
        assert producer_span_3.s != poll_span_3.s

        for topic_partition, partition_messages in messages.items():
            for message in partition_messages:
                if message.topic == "span-topic_1":
                    assert message.headers == [("x_instana_l_s", b"0")]
                elif message.topic == "span-topic_2":
                    assert message.headers == [
                        ("x_instana_l_s", b"1"),
                        (
                            "x_instana_t",
                            format_span_id(producer_span_2.t).encode("utf-8"),
                        ),
                        (
                            "x_instana_s",
                            format_span_id(producer_span_2.s).encode("utf-8"),
                        ),
                    ]

    def test_save_consumer_span_into_context(self, span: "InstanaSpan") -> None:
        """Test save_consumer_span_into_context function."""
        # Verify initial state
        assert consumer_span.get(None) is None
        assert kafka_python.consumer_token is None

        # Save span into context
        save_consumer_span_into_context(span)

        # Verify span is saved in context variable
        assert consumer_span.get(None) == span
        # Verify token is stored
        assert kafka_python.consumer_token is not None

    def test_close_consumer_span_recording_span(self, span: "InstanaSpan") -> None:
        """Test close_consumer_span with a recording span."""
        # Save span into context first
        save_consumer_span_into_context(span)
        assert kafka_python.consumer_token is not None

        # Verify span is recording
        assert span.is_recording()

        # Close the span
        close_consumer_span(span)

        # Verify span was ended and context cleared
        assert not span.is_recording()
        assert consumer_span.get(None) is None
        assert kafka_python.consumer_token is None

    def test_clear_context(self, span: "InstanaSpan") -> None:
        """Test clear_context function."""
        # Save span into context
        save_consumer_span_into_context(span)

        # Verify context has data
        assert consumer_span.get(None) == span
        assert kafka_python.consumer_token is not None

        # Clear context
        clear_context()

        # Verify all context is cleared
        assert consumer_span.get(None) is None
        assert kafka_python.consumer_token is None
