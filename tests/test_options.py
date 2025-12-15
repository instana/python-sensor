# (c) Copyright IBM Corp. 2025

import logging
import os
from typing import Generator

import pytest
from mock import patch

from instana.configurator import config
from instana.options import (
    AWSFargateOptions,
    AWSLambdaOptions,
    BaseOptions,
    EKSFargateOptions,
    GCROptions,
    ServerlessOptions,
    StandardOptions,
)


class TestBaseOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.base_options = None
        yield
        if "tracing" in config.keys():
            del config["tracing"]

    def test_base_options(self) -> None:
        if "INSTANA_DEBUG" in os.environ:
            del os.environ["INSTANA_DEBUG"]
        self.base_options = BaseOptions()

        assert not self.base_options.debug
        assert self.base_options.log_level == logging.WARN
        assert not self.base_options.extra_http_headers
        assert not self.base_options.allow_exit_as_root
        assert not self.base_options.ignore_endpoints
        assert self.base_options.kafka_trace_correlation
        assert self.base_options.secrets_matcher == "contains-ignore-case"
        assert self.base_options.secrets_list == ["key", "pass", "secret"]
        assert not self.base_options.secrets
        assert self.base_options.disabled_spans == []
        assert self.base_options.enabled_spans == []

    def test_base_options_with_config(self) -> None:
        config["tracing"] = {
            "ignore_endpoints": "service1;service3:method1,method2",
            "kafka": {"trace_correlation": True},
        }
        self.base_options = BaseOptions()
        assert self.base_options.ignore_endpoints == [
            "service1.*",
            "service3.method1",
            "service3.method2",
        ]
        assert self.base_options.kafka_trace_correlation

    @patch.dict(
        os.environ,
        {
            "INSTANA_DEBUG": "true",
            "INSTANA_EXTRA_HTTP_HEADERS": "SOMETHING;HERE",
            "INSTANA_IGNORE_ENDPOINTS": "service1;service2:method1,method2",
            "INSTANA_SECRETS": "secret1:username,password",
            "INSTANA_TRACING_DISABLE": "logging, redis,kafka",
        },
    )
    def test_base_options_with_env_vars(self) -> None:
        self.base_options = BaseOptions()
        assert self.base_options.log_level == logging.DEBUG
        assert self.base_options.debug

        assert self.base_options.extra_http_headers == ["something", "here"]

        assert self.base_options.ignore_endpoints == [
            "service1.*",
            "service2.method1",
            "service2.method2",
        ]

        assert self.base_options.secrets_matcher == "secret1"
        assert self.base_options.secrets_list == ["username", "password"]

        assert "logging" in self.base_options.disabled_spans
        assert "redis" in self.base_options.disabled_spans
        assert "kafka" in self.base_options.disabled_spans
        assert len(self.base_options.enabled_spans) == 0

    @patch.dict(
        os.environ,
        {"INSTANA_IGNORE_ENDPOINTS_PATH": "tests/util/test_configuration-1.yaml"},
    )
    def test_base_options_with_endpoint_file(self) -> None:
        self.base_options = BaseOptions()
        assert self.base_options.ignore_endpoints == [
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
        del self.base_options

    @patch.dict(
        os.environ,
        {
            "INSTANA_IGNORE_ENDPOINTS": "env_service1;env_service2:method1,method2",
            "INSTANA_KAFKA_TRACE_CORRELATION": "false",
            "INSTANA_IGNORE_ENDPOINTS_PATH": "tests/util/test_configuration-1.yaml",
            "INSTANA_TRACING_DISABLE": "logging,redis, kafka",
        },
    )
    def test_set_trace_configurations_by_env_variable(self) -> None:
        # The priority is as follows:
        # environment variables > in-code configuration >
        # > agent config (configuration.yaml) > default value

        # in-code configuration
        config["tracing"] = {}
        config["tracing"]["ignore_endpoints"] = (
            "config_service1;config_service2:method1,method2"
        )
        config["tracing"]["kafka"] = {"trace_correlation": True}
        config["tracing"]["disable"] = [{"databases": True}]

        # agent config (configuration.yaml)
        test_tracing = {
            "ignore-endpoints": "service1;service2:method1,method2",
            "disable": [
                {"messaging": True},
            ],
        }

        # Setting by env variable
        self.base_options = StandardOptions()
        self.base_options.set_tracing(test_tracing)

        assert self.base_options.ignore_endpoints == [
            "env_service1.*",
            "env_service2.method1",
            "env_service2.method2",
        ]
        assert not self.base_options.kafka_trace_correlation

        # Check disabled_spans list
        assert "logging" in self.base_options.disabled_spans
        assert "redis" in self.base_options.disabled_spans
        assert "kafka" in self.base_options.disabled_spans
        assert "databases" not in self.base_options.disabled_spans
        assert "messaging" not in self.base_options.disabled_spans
        assert len(self.base_options.enabled_spans) == 0

    @patch.dict(
        os.environ,
        {
            "INSTANA_KAFKA_TRACE_CORRELATION": "false",
            "INSTANA_IGNORE_ENDPOINTS_PATH": "tests/util/test_configuration-1.yaml",
        },
    )
    def test_set_trace_configurations_by_in_code_configuration(self) -> None:
        # The priority is as follows:
        # in-code configuration > agent config (configuration.yaml) > default value

        # in-code configuration
        config["tracing"] = {}
        config["tracing"]["ignore_endpoints"] = (
            "config_service1;config_service2:method1,method2"
        )
        config["tracing"]["kafka"] = {"trace_correlation": True}
        config["tracing"]["disable"] = [{"databases": True}]

        # agent config (configuration.yaml)
        test_tracing = {
            "ignore-endpoints": "service1;service2:method1,method2",
            "disable": [
                {"messaging": True},
            ],
        }

        self.base_options = StandardOptions()
        self.base_options.set_tracing(test_tracing)

        assert self.base_options.ignore_endpoints == [
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

        # Check disabled_spans list
        assert "databases" in self.base_options.disabled_spans
        assert "logging" not in self.base_options.disabled_spans
        assert "redis" not in self.base_options.disabled_spans
        assert "kafka" not in self.base_options.disabled_spans
        assert "messaging" not in self.base_options.disabled_spans
        assert len(self.base_options.enabled_spans) == 0

    def test_set_trace_configurations_by_in_code_variable(self) -> None:
        config["tracing"] = {}
        config["tracing"]["ignore_endpoints"] = (
            "config_service1;config_service2:method1,method2"
        )
        config["tracing"]["kafka"] = {"trace_correlation": True}
        test_tracing = {"ignore-endpoints": "service1;service2:method1,method2"}

        self.base_options = StandardOptions()
        self.base_options.set_tracing(test_tracing)

        assert self.base_options.ignore_endpoints == [
            "config_service1.*",
            "config_service2.method1",
            "config_service2.method2",
        ]
        assert self.base_options.kafka_trace_correlation

    def test_set_trace_configurations_by_agent_configuration(self) -> None:
        test_tracing = {
            "ignore-endpoints": "service1;service2:method1,method2",
            "trace-correlation": True,
            "disable": [
                {
                    "messaging": True,
                    "logging": True,
                    "kafka": False,
                },
            ],
        }

        self.base_options = StandardOptions()
        self.base_options.set_tracing(test_tracing)

        assert self.base_options.ignore_endpoints == [
            "service1.*",
            "service2.method1",
            "service2.method2",
        ]
        assert self.base_options.kafka_trace_correlation

        # Check disabled_spans list
        assert "databases" not in self.base_options.disabled_spans
        assert "logging" in self.base_options.disabled_spans
        assert "messaging" in self.base_options.disabled_spans
        assert "kafka" in self.base_options.enabled_spans

    def test_set_trace_configurations_by_default(self) -> None:
        self.base_options = StandardOptions()
        self.base_options.set_tracing({})

        assert not self.base_options.ignore_endpoints
        assert self.base_options.kafka_trace_correlation
        assert len(self.base_options.disabled_spans) == 0
        assert len(self.base_options.enabled_spans) == 0

    @patch.dict(
        os.environ,
        {"INSTANA_TRACING_DISABLE": "true"},
    )
    def test_set_trace_configurations_disable_all_tracing(self) -> None:
        self.base_options = BaseOptions()

        # All categories should be disabled
        assert "logging" in self.base_options.disabled_spans
        assert "databases" in self.base_options.disabled_spans
        assert "messaging" in self.base_options.disabled_spans
        assert "protocols" in self.base_options.disabled_spans

        # Check is_span_disabled method
        assert self.base_options.is_span_disabled(category="logging")
        assert self.base_options.is_span_disabled(category="databases")
        assert self.base_options.is_span_disabled(span_type="redis")

    @patch.dict(
        os.environ,
        {
            "INSTANA_CONFIG_PATH": "tests/util/test_configuration-1.yaml",
        },
    )
    def test_set_trace_configurations_disable_local_yaml(self) -> None:
        self.base_options = BaseOptions()

        # All categories should be disabled
        assert "logging" in self.base_options.disabled_spans
        assert "databases" in self.base_options.disabled_spans
        assert "redis" not in self.base_options.disabled_spans
        assert "redis" in self.base_options.enabled_spans

        # Check is_span_disabled method
        assert self.base_options.is_span_disabled(category="logging")
        assert self.base_options.is_span_disabled(category="databases")
        assert not self.base_options.is_span_disabled(span_type="redis")

    def test_is_span_disabled_method(self) -> None:
        self.base_options = BaseOptions()

        # Default behavior - nothing disabled
        assert not self.base_options.is_span_disabled(category="logging")
        assert not self.base_options.is_span_disabled(span_type="redis")

        # Disable a category
        self.base_options.disabled_spans = ["databases"]
        assert not self.base_options.is_span_disabled(category="logging")
        assert self.base_options.is_span_disabled(category="databases")
        assert self.base_options.is_span_disabled(span_type="redis")
        assert self.base_options.is_span_disabled(span_type="mysql")

        # Test precedence rules
        self.base_options.enabled_spans = ["redis"]
        assert self.base_options.is_span_disabled(category="databases")
        assert self.base_options.is_span_disabled(span_type="mysql")
        assert not self.base_options.is_span_disabled(span_type="redis")


class TestStandardOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.standart_options = None
        yield
        if "tracing" in config.keys():
            del config["tracing"]

    def test_standard_options(self) -> None:
        self.standart_options = StandardOptions()

        assert self.standart_options.AGENT_DEFAULT_HOST == "localhost"
        assert self.standart_options.AGENT_DEFAULT_PORT == 42699

    def test_set_secrets(self) -> None:
        self.standart_options = StandardOptions()

        test_secrets = {"matcher": "sample-match", "list": ["sample", "list"]}
        self.standart_options.set_secrets(test_secrets)
        assert self.standart_options.secrets_matcher == "sample-match"
        assert self.standart_options.secrets_list == ["sample", "list"]

    def test_set_extra_headers(self) -> None:
        self.standart_options = StandardOptions()
        test_headers = {"header1": "sample-match", "header2": ["sample", "list"]}

        self.standart_options.set_extra_headers(test_headers)
        assert self.standart_options.extra_http_headers == test_headers

    def test_set_tracing(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        self.standart_options = StandardOptions()

        test_tracing = {
            "ignore-endpoints": "service1;service2:method1,method2",
            "kafka": {"trace-correlation": "false", "header-format": "binary"},
        }
        self.standart_options.set_tracing(test_tracing)

        assert self.standart_options.ignore_endpoints == [
            "service1.*",
            "service2.method1",
            "service2.method2",
        ]
        assert not self.standart_options.kafka_trace_correlation
        assert (
            "Binary header format for Kafka is deprecated. Please use string header format."
            in caplog.messages
        )
        assert not self.standart_options.extra_http_headers

    def test_set_tracing_with_span_disabling(self) -> None:
        self.standart_options = StandardOptions()

        test_tracing = {
            "disable": [{"logging": True}, {"redis": False}, {"databases": True}]
        }
        self.standart_options.set_tracing(test_tracing)

        # Check disabled_spans and enabled_spans lists
        assert "logging" in self.standart_options.disabled_spans
        assert "databases" in self.standart_options.disabled_spans
        assert "redis" in self.standart_options.enabled_spans

        # Check is_span_disabled method
        assert self.standart_options.is_span_disabled(category="logging")
        assert self.standart_options.is_span_disabled(category="databases")
        assert self.standart_options.is_span_disabled(span_type="mysql")
        assert not self.standart_options.is_span_disabled(span_type="redis")

    def test_set_from(self) -> None:
        self.standart_options = StandardOptions()
        test_res_data = {
            "secrets": {"matcher": "sample-match", "list": ["sample", "list"]},
            "tracing": {"ignore-endpoints": "service1;service2:method1,method2"},
        }
        self.standart_options.set_from(test_res_data)

        assert (
            self.standart_options.secrets_matcher == test_res_data["secrets"]["matcher"]
        )
        assert self.standart_options.secrets_list == test_res_data["secrets"]["list"]
        assert self.standart_options.ignore_endpoints == [
            "service1.*",
            "service2.method1",
            "service2.method2",
        ]

        test_res_data = {
            "extraHeaders": {"header1": "sample-match", "header2": ["sample", "list"]},
        }
        self.standart_options.set_from(test_res_data)

        assert self.standart_options.extra_http_headers == test_res_data["extraHeaders"]

    def test_set_from_bool(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        caplog.clear()

        self.standart_options = StandardOptions()
        test_res_data = True
        self.standart_options.set_from(test_res_data)

        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert (
            "options.set_from: Wrong data type - <class 'bool'>" in caplog.messages[0]
        )

        assert self.standart_options.secrets_list == ["key", "pass", "secret"]
        assert self.standart_options.ignore_endpoints == []
        assert not self.standart_options.extra_http_headers


class TestServerlessOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.serverless_options = None
        yield

    def test_serverless_options(self) -> None:
        self.serverless_options = ServerlessOptions()

        assert not self.serverless_options.debug
        assert self.serverless_options.log_level == logging.WARN
        assert not self.serverless_options.extra_http_headers
        assert not self.serverless_options.allow_exit_as_root
        assert not self.serverless_options.ignore_endpoints
        assert self.serverless_options.secrets_matcher == "contains-ignore-case"
        assert self.serverless_options.secrets_list == ["key", "pass", "secret"]
        assert not self.serverless_options.secrets
        assert not self.serverless_options.agent_key
        assert not self.serverless_options.endpoint_url
        assert self.serverless_options.ssl_verify
        assert not self.serverless_options.endpoint_proxy
        assert self.serverless_options.timeout == 0.8

    @patch.dict(
        os.environ,
        {
            "INSTANA_AGENT_KEY": "key1",
            "INSTANA_ENDPOINT_URL": "localhost",
            "INSTANA_DISABLE_CA_CHECK": "true",
            "INSTANA_ENDPOINT_PROXY": "proxy1",
            "INSTANA_TIMEOUT": "3000",
            "INSTANA_LOG_LEVEL": "info",
        },
    )
    def test_serverless_options_with_env_vars(self) -> None:
        self.serverless_options = ServerlessOptions()

        assert self.serverless_options.agent_key == "key1"
        assert self.serverless_options.endpoint_url == "localhost"
        assert not self.serverless_options.ssl_verify
        assert self.serverless_options.endpoint_proxy == {"https": "proxy1"}
        assert self.serverless_options.timeout == 3
        assert self.serverless_options.log_level == logging.INFO


class TestAWSLambdaOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.aws_lambda_options = None
        yield

    def test_aws_lambda_options(self) -> None:
        self.aws_lambda_options = AWSLambdaOptions()

        assert not self.aws_lambda_options.agent_key
        assert not self.aws_lambda_options.endpoint_url
        assert self.aws_lambda_options.ssl_verify
        assert not self.aws_lambda_options.endpoint_proxy
        assert self.aws_lambda_options.timeout == 0.8
        assert self.aws_lambda_options.log_level == logging.WARN


class TestAWSFargateOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.aws_fargate_options = None
        yield

    def test_aws_fargate_options(self) -> None:
        self.aws_fargate_options = AWSFargateOptions()

        assert not self.aws_fargate_options.agent_key
        assert not self.aws_fargate_options.endpoint_url
        assert self.aws_fargate_options.ssl_verify
        assert not self.aws_fargate_options.endpoint_proxy
        assert self.aws_fargate_options.timeout == 0.8
        assert self.aws_fargate_options.log_level == logging.WARN
        assert not self.aws_fargate_options.tags
        assert not self.aws_fargate_options.zone

    @patch.dict(
        os.environ,
        {
            "INSTANA_AGENT_KEY": "key1",
            "INSTANA_ENDPOINT_URL": "localhost",
            "INSTANA_DISABLE_CA_CHECK": "true",
            "INSTANA_ENDPOINT_PROXY": "proxy1",
            "INSTANA_TIMEOUT": "3000",
            "INSTANA_LOG_LEVEL": "info",
            "INSTANA_TAGS": "key1=value1,key2=value2",
            "INSTANA_ZONE": "zone1",
        },
    )
    def test_aws_fargate_options_with_env_vars(self) -> None:
        self.aws_fargate_options = AWSFargateOptions()

        assert self.aws_fargate_options.agent_key == "key1"
        assert self.aws_fargate_options.endpoint_url == "localhost"
        assert not self.aws_fargate_options.ssl_verify
        assert self.aws_fargate_options.endpoint_proxy == {"https": "proxy1"}
        assert self.aws_fargate_options.timeout == 3
        assert self.aws_fargate_options.log_level == logging.INFO

        assert self.aws_fargate_options.tags == {"key1": "value1", "key2": "value2"}
        assert self.aws_fargate_options.zone == "zone1"


class TestEKSFargateOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.eks_fargate_options = None
        yield

    def test_eks_fargate_options(self) -> None:
        self.eks_fargate_options = EKSFargateOptions()

        assert not self.eks_fargate_options.agent_key
        assert not self.eks_fargate_options.endpoint_url
        assert self.eks_fargate_options.ssl_verify
        assert not self.eks_fargate_options.endpoint_proxy
        assert self.eks_fargate_options.timeout == 0.8
        assert self.eks_fargate_options.log_level == logging.WARN

    @patch.dict(
        os.environ,
        {
            "INSTANA_AGENT_KEY": "key1",
            "INSTANA_ENDPOINT_URL": "localhost",
            "INSTANA_DISABLE_CA_CHECK": "true",
            "INSTANA_ENDPOINT_PROXY": "proxy1",
            "INSTANA_TIMEOUT": "3000",
            "INSTANA_LOG_LEVEL": "info",
        },
    )
    def test_eks_fargate_options_with_env_vars(self) -> None:
        self.eks_fargate_options = EKSFargateOptions()

        assert self.eks_fargate_options.agent_key == "key1"
        assert self.eks_fargate_options.endpoint_url == "localhost"
        assert not self.eks_fargate_options.ssl_verify
        assert self.eks_fargate_options.endpoint_proxy == {"https": "proxy1"}
        assert self.eks_fargate_options.timeout == 3
        assert self.eks_fargate_options.log_level == logging.INFO


class TestGCROptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.gcr_options = None
        yield

    def test_gcr_options(self) -> None:
        self.gcr_options = GCROptions()

        assert not self.gcr_options.debug
        assert self.gcr_options.log_level == logging.WARN
        assert not self.gcr_options.extra_http_headers
        assert not self.gcr_options.allow_exit_as_root
        assert not self.gcr_options.ignore_endpoints
        assert self.gcr_options.secrets_matcher == "contains-ignore-case"
        assert self.gcr_options.secrets_list == ["key", "pass", "secret"]
        assert not self.gcr_options.secrets
        assert not self.gcr_options.agent_key
        assert not self.gcr_options.endpoint_url
        assert self.gcr_options.ssl_verify
        assert not self.gcr_options.endpoint_proxy
        assert self.gcr_options.timeout == 0.8

    @patch.dict(
        os.environ,
        {
            "INSTANA_AGENT_KEY": "key1",
            "INSTANA_ENDPOINT_URL": "localhost",
            "INSTANA_DISABLE_CA_CHECK": "true",
            "INSTANA_ENDPOINT_PROXY": "proxy1",
            "INSTANA_TIMEOUT": "3000",
            "INSTANA_LOG_LEVEL": "info",
        },
    )
    def test_gcr_options_with_env_vars(self) -> None:
        self.gcr_options = GCROptions()

        assert self.gcr_options.agent_key == "key1"
        assert self.gcr_options.endpoint_url == "localhost"
        assert not self.gcr_options.ssl_verify
        assert self.gcr_options.endpoint_proxy == {"https": "proxy1"}
        assert self.gcr_options.timeout == 3
        assert self.gcr_options.log_level == logging.INFO


class TestStackTraceConfiguration:
    """Test stack trace configuration options."""

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.options = None
        yield
        if "tracing" in config.keys():
            del config["tracing"]

    def test_stack_trace_defaults(self) -> None:
        """Test default stack trace configuration."""
        self.options = BaseOptions()
        
        assert self.options.stack_trace_level == "all"
        assert self.options.stack_trace_length == 30
        assert self.options.stack_trace_technology_config == {}

    @pytest.mark.parametrize(
        "level_value,expected_level",
        [
            ("error", "error"),
            ("none", "none"),
            ("all", "all"),
            ("ERROR", "error"),  # Case insensitive
        ],
    )
    def test_stack_trace_level_env_var(
        self,
        level_value: str,
        expected_level: str,
    ) -> None:
        """Test INSTANA_STACK_TRACE environment variable with valid values."""
        with patch.dict(os.environ, {"INSTANA_STACK_TRACE": level_value}):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == expected_level
            assert self.options.stack_trace_length == 30  # Default

    def test_stack_trace_level_env_var_invalid(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test INSTANA_STACK_TRACE with invalid value falls back to default."""
        caplog.set_level(logging.WARNING, logger="instana")
        with patch.dict(os.environ, {"INSTANA_STACK_TRACE": "INVALID"}):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == "all"  # Falls back to default
            assert any(
                "Invalid INSTANA_STACK_TRACE value" in message
                for message in caplog.messages
            )

    @pytest.mark.parametrize(
        "length_value,expected_length",
        [
            ("25", 25),  
            ("60", 60),  # Not capped here, capped when add_stack() is called
        ],
    )
    def test_stack_trace_length_env_var(
        self,
        length_value: str,
        expected_length: int,
    ) -> None:
        """Test INSTANA_STACK_TRACE_LENGTH environment variable with valid values."""
        with patch.dict(os.environ, {"INSTANA_STACK_TRACE_LENGTH": length_value}):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == "all"  # Default
            assert self.options.stack_trace_length == expected_length

    @pytest.mark.parametrize(
        "length_value,expected_warning",
        [
            ("0", "must be positive"),
            ("-5", "must be positive"),
            ("invalid", "Invalid INSTANA_STACK_TRACE_LENGTH"),
        ],
    )
    def test_stack_trace_length_env_var_invalid(
        self,
        caplog: pytest.LogCaptureFixture,
        length_value: str,
        expected_warning: str,
    ) -> None:
        """Test INSTANA_STACK_TRACE_LENGTH with invalid values."""
        caplog.set_level(logging.WARNING, logger="instana")
        with patch.dict(os.environ, {"INSTANA_STACK_TRACE_LENGTH": length_value}):
            self.options = BaseOptions()
            assert self.options.stack_trace_length == 30  # Falls back to default
            assert any(expected_warning in message for message in caplog.messages)

    def test_stack_trace_both_env_vars(self) -> None:
        """Test both INSTANA_STACK_TRACE and INSTANA_STACK_TRACE_LENGTH."""
        with patch.dict(
            os.environ,
            {
                "INSTANA_STACK_TRACE": "error",
                "INSTANA_STACK_TRACE_LENGTH": "15",
            },
        ):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == "error"
            assert self.options.stack_trace_length == 15

    def test_stack_trace_in_code_config(self) -> None:
        """Test in-code configuration for stack trace."""
        config["tracing"] = {
            "global": {
                "stack_trace": "error",
                "stack_trace_length": 20
            }
        }
        self.options = BaseOptions()
        assert self.options.stack_trace_level == "error"
        assert self.options.stack_trace_length == 20

    def test_stack_trace_agent_config(self) -> None:
        """Test agent configuration for stack trace."""
        self.options = StandardOptions()
        
        test_tracing = {
            "global": {
                "stack-trace": "error",
                "stack-trace-length": 15
            }
        }
        self.options.set_tracing(test_tracing)
        
        assert self.options.stack_trace_level == "error"
        assert self.options.stack_trace_length == 15

    def test_stack_trace_precedence_env_over_in_code(self) -> None:
        """Test environment variables take precedence over in-code config."""
        config["tracing"] = {
            "global": {
                "stack_trace": "all",
                "stack_trace_length": 10
            }
        }
        
        with patch.dict(
            os.environ,
            {
                "INSTANA_STACK_TRACE": "error",
                "INSTANA_STACK_TRACE_LENGTH": "25",
            },
        ):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == "error"
            assert self.options.stack_trace_length == 25

    def test_stack_trace_precedence_in_code_over_agent(self) -> None:
        """Test in-code config takes precedence over agent config."""
        config["tracing"] = {
            "global": {
                "stack_trace": "error",
                "stack_trace_length": 20
            }
        }
        
        self.options = StandardOptions()
        
        test_tracing = {
            "global": {
                "stack-trace": "all",
                "stack-trace-length": 10
            }
        }
        self.options.set_tracing(test_tracing)
        
        # In-code config should win
        assert self.options.stack_trace_level == "error"
        assert self.options.stack_trace_length == 20

    def test_stack_trace_technology_specific_override(self) -> None:
        """Test technology-specific stack trace configuration."""
        self.options = StandardOptions()
        
        test_tracing = {
            "global": {
                "stack-trace": "error",
                "stack-trace-length": 25
            },
            "kafka": {
                "stack-trace": "all",
                "stack-trace-length": 35
            },
            "redis": {
                "stack-trace": "none"
            }
        }
        self.options.set_tracing(test_tracing)
        
        # Global config
        assert self.options.stack_trace_level == "error"
        assert self.options.stack_trace_length == 25
        
        # Kafka-specific override
        level, length = self.options.get_stack_trace_config("kafka-producer")
        assert level == "all"
        assert length == 35
        
        # Redis-specific override (inherits length from global)
        level, length = self.options.get_stack_trace_config("redis")
        assert level == "none"
        assert length == 25
        
        # Non-overridden span uses global
        level, length = self.options.get_stack_trace_config("mysql")
        assert level == "error"
        assert length == 25

    def test_get_stack_trace_config_with_hyphenated_span_name(self) -> None:
        """Test get_stack_trace_config extracts technology name correctly."""
        self.options = StandardOptions()
        self.options.stack_trace_technology_config = {
            "kafka": {"level": "all", "length": 35}
        }
        
        # Should match "kafka" from "kafka-producer"
        level, length = self.options.get_stack_trace_config("kafka-producer")
        assert level == "all"
        assert length == 35
        
        # Should match "kafka" from "kafka-consumer"
        level, length = self.options.get_stack_trace_config("kafka-consumer")
        assert level == "all"
        assert length == 35

    def test_stack_trace_yaml_config_basic(self) -> None:
        """Test YAML configuration for stack trace (basic format)."""
        with patch.dict(
            os.environ,
            {"INSTANA_CONFIG_PATH": "tests/util/test_stack_trace_config_1.yaml"},
        ):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == "all"
            assert self.options.stack_trace_length == 15

    def test_stack_trace_yaml_config_with_prefix(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test YAML configuration with com.instana prefix."""
        caplog.set_level(logging.WARNING, logger="instana")
        with patch.dict(
            os.environ,
            {"INSTANA_CONFIG_PATH": "tests/util/test_stack_trace_config_2.yaml"},
        ):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == "error"
            assert self.options.stack_trace_length == 20

            assert (
            'Please use "tracing" instead of "com.instana.tracing" for local configuration file.'
            in caplog.messages
        )

    def test_stack_trace_yaml_config_disabled(self) -> None:
        """Test YAML configuration with stack trace disabled."""
        with patch.dict(
            os.environ,
            {"INSTANA_CONFIG_PATH": "tests/util/test_stack_trace_config_3.yaml"},
        ):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == "none"
            assert self.options.stack_trace_length == 5

    def test_stack_trace_yaml_config_invalid(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test YAML configuration with invalid values."""
        caplog.set_level(logging.WARNING, logger="instana")
        with patch.dict(
            os.environ,
            {"INSTANA_CONFIG_PATH": "tests/util/test_stack_trace_config_4.yaml"},
        ):
            self.options = BaseOptions()
            # Should fall back to defaults
            assert self.options.stack_trace_level == "all"
            assert self.options.stack_trace_length == 30
            assert any(
                "Invalid stack-trace value" in message
                for message in caplog.messages
            )
            assert any(
                "must be positive" in message
                for message in caplog.messages
            )

    def test_stack_trace_yaml_config_partial(self) -> None:
        """Test YAML configuration with only stack-trace (no length)."""
        with patch.dict(
            os.environ,
            {"INSTANA_CONFIG_PATH": "tests/util/test_stack_trace_config_5.yaml"},
        ):
            self.options = BaseOptions()
            assert self.options.stack_trace_level == "error"
            assert self.options.stack_trace_length == 30  # Default

    def test_stack_trace_precedence_env_over_yaml(self) -> None:
        """Test environment variables take precedence over YAML config."""
        with patch.dict(
            os.environ,
            {
                "INSTANA_CONFIG_PATH": "tests/util/test_stack_trace_config_1.yaml",
                "INSTANA_STACK_TRACE": "error",
                "INSTANA_STACK_TRACE_LENGTH": "25",
            },
        ):
            self.options = BaseOptions()
            # Env vars should override YAML
            assert self.options.stack_trace_level == "error"
            assert self.options.stack_trace_length == 25

    def test_stack_trace_precedence_yaml_over_in_code(self) -> None:
        """Test YAML config takes precedence over in-code config."""
        config["tracing"] = {
            "global": {
                "stack_trace": "error",
                "stack_trace_length": 10
            }
        }
        
        with patch.dict(
            os.environ,
            {"INSTANA_CONFIG_PATH": "tests/util/test_stack_trace_config_1.yaml"},
        ):
            self.options = BaseOptions()
            # YAML should override in-code config
            assert self.options.stack_trace_level == "all"
            assert self.options.stack_trace_length == 15

    def test_stack_trace_precedence_yaml_over_agent(self) -> None:
        """Test YAML config takes precedence over agent config."""
        with patch.dict(
            os.environ,
            {"INSTANA_CONFIG_PATH": "tests/util/test_stack_trace_config_2.yaml"},
        ):
            self.options = StandardOptions()
            
            test_tracing = {
                "global": {
                    "stack-trace": "all",
                    "stack-trace-length": 30
                }
            }
            self.options.set_tracing(test_tracing)
            
            # YAML should override agent config
            assert self.options.stack_trace_level == "error"
            assert self.options.stack_trace_length == 20
