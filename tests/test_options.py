# (c) Copyright IBM Corp. 2025

import logging
import os
from typing import Generator

from mock import patch
import pytest

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
        },
    )
    def test_set_trace_configurations_by_env_variable(self) -> None:
        # The priority is as follows:
        # environment variables > in-code configuration >
        # > agent config (configuration.yaml) > default value
        config["tracing"]["ignore_endpoints"] = (
            "config_service1;config_service2:method1,method2"
        )
        config["tracing"]["kafka"] = {"trace_correlation": True}
        test_tracing = {"ignore-endpoints": "service1;service2:method1,method2"}

        # Setting by env variable
        self.base_options = StandardOptions()
        self.base_options.set_tracing(test_tracing)

        assert self.base_options.ignore_endpoints == [
            "env_service1.*",
            "env_service2.method1",
            "env_service2.method2",
        ]
        assert not self.base_options.kafka_trace_correlation

    @patch.dict(
        os.environ,
        {
            "INSTANA_KAFKA_TRACE_CORRELATION": "false",
            "INSTANA_IGNORE_ENDPOINTS_PATH": "tests/util/test_configuration-1.yaml",
        },
    )
    def test_set_trace_configurations_by_local_configuration_file(self) -> None:
        config["tracing"]["ignore_endpoints"] = (
            "config_service1;config_service2:method1,method2"
        )
        config["tracing"]["kafka"] = {"trace_correlation": True}
        test_tracing = {"ignore-endpoints": "service1;service2:method1,method2"}

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

    def test_set_trace_configurations_by_in_code_variable(self) -> None:
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
        }

        self.base_options = StandardOptions()
        self.base_options.set_tracing(test_tracing)

        assert self.base_options.ignore_endpoints == [
            "service1.*",
            "service2.method1",
            "service2.method2",
        ]
        assert self.base_options.kafka_trace_correlation

    def test_set_trace_configurations_by_default(self) -> None:
        self.base_options = StandardOptions()
        self.base_options.set_tracing({})

        assert not self.base_options.ignore_endpoints
        assert self.base_options.kafka_trace_correlation


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
