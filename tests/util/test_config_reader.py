# (c) Copyright IBM Corp. 2025

import logging
import os
from typing import TYPE_CHECKING, Generator

import pytest
from yaml import YAMLError

from instana.options import BaseOptions
from instana.util.config import (
    get_disable_trace_configurations_from_yaml,
    get_http_exit_classification_from_yaml,
    parse_filter_rules_yaml,
)
from instana.util.config_reader import ConfigReader

if TYPE_CHECKING:
    from pytest import LogCaptureFixture
    from pytest_mock import MockerFixture


class TestConfigReader:
    @pytest.fixture(autouse=True)
    def _resource(
        self,
        caplog: "LogCaptureFixture",
    ) -> Generator[None, None, None]:
        yield
        caplog.clear()
        if "INSTANA_CONFIG_PATH" in os.environ:
            os.environ.pop("INSTANA_CONFIG_PATH")

    def test_config_reader_null(self, caplog: "LogCaptureFixture") -> None:
        config_reader = ConfigReader(os.environ.get("INSTANA_CONFIG_PATH", ""))
        assert config_reader.file_path == ""
        assert config_reader.data == {}
        assert "ConfigReader: No configuration file specified" in caplog.messages

    def test_config_reader_default(self) -> None:
        filename = "tests/util/test_configuration-1.yaml"
        os.environ["INSTANA_CONFIG_PATH"] = filename
        config_reader = ConfigReader(os.environ.get("INSTANA_CONFIG_PATH", ""))
        assert config_reader.file_path == filename
        assert "tracing" in config_reader.data
        assert len(config_reader.data["tracing"]) == 3

    def test_config_reader_file_not_found_error(
        self, caplog: "LogCaptureFixture"
    ) -> None:
        filename = "tests/util/test_configuration-3.yaml"
        os.environ["INSTANA_CONFIG_PATH"] = filename
        config_reader = ConfigReader(os.environ.get("INSTANA_CONFIG_PATH", ""))
        assert config_reader.file_path == filename
        assert config_reader.data == {}
        assert (
            f"ConfigReader: Configuration file has not found: {filename}"
            in caplog.messages
        )

    def test_config_reader_yaml_error(
        self, caplog: "LogCaptureFixture", mocker: "MockerFixture"
    ) -> None:
        filename = "tests/util/test_configuration-1.yaml"
        exception_message = "BLAH"
        mocker.patch(
            "instana.util.config_reader.yaml.safe_load",
            side_effect=YAMLError(exception_message),
        )

        config_reader = ConfigReader(filename)  # noqa: F841
        assert (
            f"ConfigReader: Error parsing YAML file: {exception_message}"
            in caplog.messages
        )

    def test_load_configuration_with_tracing(self, caplog: "LogCaptureFixture") -> None:
        caplog.set_level(logging.DEBUG, logger="instana")

        span_filters = parse_filter_rules_yaml("tests/util/test_configuration-1.yaml")
        # test with tracing
        assert span_filters == {
            "exclude": [
                {
                    "name": "Redis",
                    "suppression": True,
                    "attributes": [
                        {"key": "command", "values": ["get"], "match_type": "strict"},
                        {"key": "get", "values": ["type"], "match_type": "strict"},
                    ],
                },
                {
                    "name": "DynamoDB",
                    "suppression": True,
                    "attributes": [
                        {"key": "op", "values": ["query"], "match_type": "strict"},
                    ],
                },
                {
                    "name": "Kafka",
                    "suppression": True,
                    "attributes": [
                        {
                            "key": "kafka.access",
                            "values": ["consume", "send", "produce"],
                            "match_type": "contains",
                        },
                        {
                            "key": "kafka.service",
                            "values": ["span-topic", "topic1", "topic2"],
                            "match_type": "strict",
                        },
                        {
                            "key": "kafka.access",
                            "values": ["*"],
                            "match_type": "strict",
                        },
                    ],
                },
                {
                    "name": "Protocols Category",
                    "suppression": True,
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["protocols"],
                            "match_type": "strict",
                        }
                    ],
                },
                {
                    "name": "Entry Span Kind",
                    "suppression": True,
                    "attributes": [
                        {
                            "key": "kind",
                            "values": ["intermediate"],
                            "match_type": "strict",
                        }
                    ],
                },
            ],
            "include": [
                {
                    "name": "Kafka Producer",
                    "suppression": None,
                    "attributes": [
                        {"key": "type", "values": ["kafka"], "match_type": "strict"},
                        {"key": "kind", "values": ["exit"], "match_type": "strict"},
                        {
                            "key": "kafka.service",
                            "values": ["topic"],
                            "match_type": "contains",
                        },
                    ],
                }
            ],
        }

        os.environ["INSTANA_CONFIG_PATH"] = "tests/util/test_configuration-1.yaml"
        disabled_spans, enabled_spans = get_disable_trace_configurations_from_yaml()
        # Check disabled_spans list
        assert "logging" in disabled_spans
        assert "databases" in disabled_spans
        assert "redis" not in disabled_spans
        assert "redis" in enabled_spans

        # Check HTTP exit 4xx classification (classify-as-errors: [401, 403])
        classify_all, codes = get_http_exit_classification_from_yaml()
        assert classify_all is False
        assert codes == [401, 403]

        assert (
            'Please use "tracing" instead of "com.instana.tracing" for local configuration file.'
            not in caplog.messages
        )

    def test_load_configuration_legacy(self, caplog: "LogCaptureFixture") -> None:
        caplog.set_level(logging.DEBUG, logger="instana")

        span_filters = parse_filter_rules_yaml("tests/util/test_configuration-2.yaml")
        assert span_filters == {
            "exclude": [
                {
                    "name": "Redis",
                    "suppression": True,
                    "attributes": [
                        {"key": "command", "values": ["get"], "match_type": "strict"},
                        {"key": "get", "values": ["type"], "match_type": "strict"},
                    ],
                },
                {
                    "name": "DynamoDB",
                    "suppression": True,
                    "attributes": [
                        {"key": "op", "values": ["query"], "match_type": "strict"},
                    ],
                },
                {
                    "name": "Kafka",
                    "suppression": True,
                    "attributes": [
                        {
                            "key": "kafka.access",
                            "values": ["consume", "send", "produce"],
                            "match_type": "contains",
                        },
                        {
                            "key": "kafka.service",
                            "values": ["span-topic", "topic1", "topic2"],
                            "match_type": "strict",
                        },
                        {
                            "key": "kafka.access",
                            "values": ["*"],
                            "match_type": "strict",
                        },
                    ],
                },
            ],
            "include": [],
        }

        os.environ["INSTANA_CONFIG_PATH"] = "tests/util/test_configuration-2.yaml"
        disabled_spans, enabled_spans = get_disable_trace_configurations_from_yaml()
        # Check disabled_spans list
        assert "logging" in disabled_spans
        assert "databases" in disabled_spans
        assert "redis" not in disabled_spans
        assert "redis" in enabled_spans

        # Check HTTP exit 4xx classification (classify-all-4xx-as-errors: true)
        classify_all, codes = get_http_exit_classification_from_yaml()
        assert classify_all is True
        assert codes == []

        assert (
            'Please use "tracing" instead of "com.instana.tracing" for local configuration file.'
            in caplog.messages
        )

    def test_base_options_yaml_classify_as_errors(self) -> None:
        """BaseOptions reads classify-as-errors codes from YAML (test_configuration-1.yaml)."""
        os.environ["INSTANA_CONFIG_PATH"] = "tests/util/test_configuration-1.yaml"
        opts = BaseOptions()
        assert opts.http_exit_classify_as_errors == [401, 403]
        assert opts.http_exit_classify_all_4xx_as_errors is False

    def test_base_options_yaml_classify_all_4xx(self) -> None:
        """BaseOptions reads classify-all-4xx-as-errors from YAML (test_configuration-2.yaml)."""
        os.environ["INSTANA_CONFIG_PATH"] = "tests/util/test_configuration-2.yaml"
        opts = BaseOptions()
        assert opts.http_exit_classify_all_4xx_as_errors is True
        assert opts.http_exit_classify_as_errors == []

    def test_base_options_yaml_http_env_var_takes_precedence(self) -> None:
        """Env var overrides YAML http classification."""
        os.environ["INSTANA_CONFIG_PATH"] = "tests/util/test_configuration-1.yaml"
        os.environ["INSTANA_TRACING_HTTP_EXIT_CLASSIFY_ALL_4XX_AS_ERRORS"] = "true"
        opts = BaseOptions()
        # YAML says [401, 403] via classify-as-errors, but env var (classify_all) takes precedence
        assert opts.http_exit_classify_all_4xx_as_errors is True
        assert opts.http_exit_classify_as_errors == []
        os.environ.pop("INSTANA_TRACING_HTTP_EXIT_CLASSIFY_ALL_4XX_AS_ERRORS")
