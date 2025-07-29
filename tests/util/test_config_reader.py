# (c) Copyright IBM Corp. 2025

import logging
import os

import pytest

from instana.util.config import (
    get_disable_trace_configurations_from_yaml,
    parse_ignored_endpoints_from_yaml,
)


class TestConfigReader:
    def test_load_configuration_with_tracing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")

        ignore_endpoints = parse_ignored_endpoints_from_yaml(
            "tests/util/test_configuration-1.yaml"
        )
        # test with tracing
        assert ignore_endpoints == [
            "redis.get",
            "redis.type",
            "dynamodb.query",
            "kafka.consume.span-topic",
            "kafka.consume.topic1",
            "kafka.consume.topic2",
            "kafka.send.span-topic",
            "kafka.send.topic1",
            "kafka.send.topic2",
            "kafka.consume.topic3",
            "kafka.*.span-topic",
            "kafka.*.topic4",
        ]

        os.environ["INSTANA_CONFIG_PATH"] = "tests/util/test_configuration-1.yaml"
        disabled_spans, enabled_spans = get_disable_trace_configurations_from_yaml()
        # Check disabled_spans list
        assert "logging" in disabled_spans
        assert "databases" in disabled_spans
        assert "redis" not in disabled_spans
        assert "redis" in enabled_spans

        assert (
            'Please use "tracing" instead of "com.instana.tracing" for local configuration file.'
            not in caplog.messages
        )

    def test_load_configuration_legacy(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")

        ignore_endpoints = parse_ignored_endpoints_from_yaml(
            "tests/util/test_configuration-2.yaml"
        )
        assert ignore_endpoints == [
            "redis.get",
            "redis.type",
            "dynamodb.query",
            "kafka.send.*",
            "kafka.consume.span-topic",
            "kafka.consume.topic1",
            "kafka.consume.topic2",
            "kafka.send.span-topic",
            "kafka.send.topic1",
            "kafka.send.topic2",
            "kafka.consume.topic3",
            "kafka.*.span-topic",
            "kafka.*.topic4",
        ]

        os.environ["INSTANA_CONFIG_PATH"] = "tests/util/test_configuration-2.yaml"
        disabled_spans, enabled_spans = get_disable_trace_configurations_from_yaml()
        # Check disabled_spans list
        assert "logging" in disabled_spans
        assert "databases" in disabled_spans
        assert "redis" not in disabled_spans
        assert "redis" in enabled_spans

        assert (
            'Please use "tracing" instead of "com.instana.tracing" for local configuration file.'
            in caplog.messages
        )
