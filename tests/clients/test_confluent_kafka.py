# (c) Copyright IBM Corp. 2025

from typing import Generator

import pytest
from confluent_kafka import Consumer, KafkaException, Producer  # noqa: F401
from confluent_kafka.admin import AdminClient, NewTopic
from opentelemetry.trace import SpanKind

from instana.singletons import agent, tracer
from tests.helpers import testenv


class TestConfluentKafkaProducer:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # Kafka admin client

        self.kafka_config = {"bootstrap.servers": testenv["kafka_bootstrap_servers"]}

        self.kafka_client = AdminClient(self.config, client_id="test_confluent_kafka")

        try:
            topics = self.kafka_client.create_topics(  # noqa: F841
                [
                    NewTopic(
                        testenv["kafka_topic"],
                        num_partitions=1,
                        replication_factor=1,
                    ),
                ]
            )
        except KafkaException:
            pass

        # Kafka producer
        self.producer = Producer(self.config)
        yield
        # teardown
        # Ensure that allow_exit_as_root has the default value"""
        agent.options.allow_exit_as_root = False
        # Close connections
        self.producer.close()
        self.kafka_client.delete_topics([testenv["kafka_topic"]])
        self.kafka_client.close()

    def test_trace_kafka_produce(self) -> None:
        with tracer.start_as_current_span("test"):
            self.producer.produce(testenv["kafka_topic"], b"raw_bytes")

        # record_metadata = future.get(timeout=10)  # noqa: F841

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

    # def test_trace_kafka_consume(self) -> None:
    #     agent.options.allow_exit_as_root = False

    #     # Produce some events
    #     self.producer.send(testenv["kafka_topic"], b"raw_bytes1")
    #     self.producer.send(testenv["kafka_topic"], b"raw_bytes2")
    #     self.producer.flush()

    #     # Consume the events
    #     consumer = KafkaConsumer(
    #         testenv["kafka_topic"],
    #         bootstrap_servers=testenv["kafka_bootstrap_servers"],
    #         auto_offset_reset="earliest",  # consume earliest available messages
    #         enable_auto_commit=False,  # do not auto-commit offsets
    #         consumer_timeout_ms=1000,
    #     )

    #     with tracer.start_as_current_span("test"):
    #         for msg in consumer:
    #             if msg is None:
    #                 break

    #     consumer.close()

    #     spans = self.recorder.queued_spans()
    #     assert len(spans) == 4

    #     kafka_span = spans[0]
    #     test_span = spans[len(spans) - 1]

    #     # Same traceId
    #     assert test_span.t == kafka_span.t

    #     # Parent relationships
    #     assert kafka_span.p == test_span.s

    #     # Error logging
    #     assert not test_span.ec
    #     assert not kafka_span.ec

    #     assert kafka_span.n == "kafka"
    #     assert kafka_span.k == SpanKind.SERVER
    #     assert kafka_span.data["kafka"]["service"] == testenv["kafka_topic"]
    #     assert kafka_span.data["kafka"]["access"] == "consume"
