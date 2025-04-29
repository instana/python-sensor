import logging
import os
from typing import Generator

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

env_vars = [
    "INSTANA_DEBUG",
    "INSTANA_EXTRA_HTTP_HEADERS",
    "INSTANA_IGNORE_ENDPOINTS",
    "INSTANA_SECRETS",
    "INSTANA_AGENT_KEY",
    "INSTANA_ENDPOINT_URL",
    "INSTANA_DISABLE_CA_CHECK",
    "INSTANA_ENDPOINT_PROXY",
    "INSTANA_TIMEOUT",
    "INSTANA_LOG_LEVEL",
]


def clean_env_vars():
    for env_var in env_vars:
        if env_var in os.environ.keys():
            del os.environ[env_var]


class TestBaseOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield
        clean_env_vars()
        if "tracing" in config.keys():
            del config["tracing"]

    def test_base_options(self) -> None:
        if "INSTANA_DEBUG" in os.environ:
            del os.environ["INSTANA_DEBUG"]
        test_base_options = BaseOptions()

        assert not test_base_options.debug
        assert test_base_options.log_level == logging.WARN
        assert not test_base_options.extra_http_headers
        assert not test_base_options.allow_exit_as_root
        assert not test_base_options.ignore_endpoints
        assert test_base_options.secrets_matcher == "contains-ignore-case"
        assert test_base_options.secrets_list == ["key", "pass", "secret"]
        assert not test_base_options.secrets

    def test_base_options_with_config(self) -> None:
        config["tracing"]["ignore_endpoints"] = "service1;service3:endpoint1,endpoint2"
        test_base_options = BaseOptions()
        assert test_base_options.ignore_endpoints == [
            "service1",
            "service3.endpoint1",
            "service3.endpoint2",
        ]

    def test_base_options_with_env_vars(self) -> None:
        os.environ["INSTANA_DEBUG"] = "true"
        os.environ["INSTANA_EXTRA_HTTP_HEADERS"] = "SOMETHING;HERE"
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "service1;service2:endpoint1,endpoint2"
        os.environ["INSTANA_SECRETS"] = "secret1:username,password"

        test_base_options = BaseOptions()
        assert test_base_options.log_level == logging.DEBUG
        assert test_base_options.debug

        assert test_base_options.extra_http_headers == ["something", "here"]

        assert test_base_options.ignore_endpoints == [
            "service1",
            "service2.endpoint1",
            "service2.endpoint2",
        ]

        assert test_base_options.secrets_matcher == "secret1"
        assert test_base_options.secrets_list == ["username", "password"]


class TestStandardOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield
        clean_env_vars()
        if "tracing" in config.keys():
            del config["tracing"]

    def test_standard_options(self) -> None:
        test_standard_options = StandardOptions()

        assert test_standard_options.AGENT_DEFAULT_HOST == "localhost"
        assert test_standard_options.AGENT_DEFAULT_PORT == 42699

    def test_set_secrets(self) -> None:
        test_standard_options = StandardOptions()

        test_secrets = {"matcher": "sample-match", "list": ["sample", "list"]}
        test_standard_options.set_secrets(test_secrets)
        assert test_standard_options.secrets_matcher == "sample-match"
        assert test_standard_options.secrets_list == ["sample", "list"]

    def test_set_extra_headers(self) -> None:
        test_standard_options = StandardOptions()
        test_headers = {"header1": "sample-match", "header2": ["sample", "list"]}

        test_standard_options.set_extra_headers(test_headers)
        assert test_standard_options.extra_http_headers == test_headers

    def test_set_tracing(self) -> None:
        test_standard_options = StandardOptions()

        test_tracing = {"ignore-endpoints": "service1;service2:endpoint1,endpoint2"}
        test_standard_options.set_tracing(test_tracing)

        assert test_standard_options.ignore_endpoints == [
            "service1",
            "service2.endpoint1",
            "service2.endpoint2",
        ]
        assert not test_standard_options.extra_http_headers

    def test_set_tracing_priority(self) -> None:
        # Environment variables > In-code Configuration > Agent Configuration
        # First test when all attributes given
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = (
            "env_service1;env_service2:endpoint1,endpoint2"
        )
        config["tracing"]["ignore_endpoints"] = (
            "config_service1;config_service2:endpoint1,endpoint2"
        )
        test_tracing = {"ignore-endpoints": "service1;service2:endpoint1,endpoint2"}

        test_standard_options = StandardOptions()
        test_standard_options.set_tracing(test_tracing)

        assert test_standard_options.ignore_endpoints == [
            "env_service1",
            "env_service2.endpoint1",
            "env_service2.endpoint2",
        ]

        # Second test when In-code configuration and Agent configuration given

        del os.environ["INSTANA_IGNORE_ENDPOINTS"]

        test_standard_options = StandardOptions()
        test_standard_options.set_tracing(test_tracing)

        assert test_standard_options.ignore_endpoints == [
            "config_service1",
            "config_service2.endpoint1",
            "config_service2.endpoint2",
        ]

    def test_set_from(self) -> None:
        test_standard_options = StandardOptions()
        test_res_data = {
            "secrets": {"matcher": "sample-match", "list": ["sample", "list"]},
            "tracing": {"ignore-endpoints": "service1;service2:endpoint1,endpoint2"},
        }
        test_standard_options.set_from(test_res_data)

        assert (
            test_standard_options.secrets_matcher == test_res_data["secrets"]["matcher"]
        )
        assert test_standard_options.secrets_list == test_res_data["secrets"]["list"]
        assert test_standard_options.ignore_endpoints == [
            "service1",
            "service2.endpoint1",
            "service2.endpoint2",
        ]

        test_res_data = {
            "extraHeaders": {"header1": "sample-match", "header2": ["sample", "list"]},
        }
        test_standard_options.set_from(test_res_data)

        assert test_standard_options.extra_http_headers == test_res_data["extraHeaders"]

    def test_set_from_bool(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        caplog.clear()

        test_standard_options = StandardOptions()
        test_res_data = True
        test_standard_options.set_from(test_res_data)

        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert (
            "options.set_from: Wrong data type - <class 'bool'>" in caplog.messages[0]
        )

        assert test_standard_options.secrets_list == ["key", "pass", "secret"]
        assert test_standard_options.ignore_endpoints == []
        assert not test_standard_options.extra_http_headers


class TestServerlessOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield
        clean_env_vars()

    def test_serverless_options(self) -> None:
        test_serverless_options = ServerlessOptions()

        assert not test_serverless_options.debug
        assert test_serverless_options.log_level == logging.WARN
        assert not test_serverless_options.extra_http_headers
        assert not test_serverless_options.allow_exit_as_root
        assert not test_serverless_options.ignore_endpoints
        assert test_serverless_options.secrets_matcher == "contains-ignore-case"
        assert test_serverless_options.secrets_list == ["key", "pass", "secret"]
        assert not test_serverless_options.secrets
        assert not test_serverless_options.agent_key
        assert not test_serverless_options.endpoint_url
        assert test_serverless_options.ssl_verify
        assert not test_serverless_options.endpoint_proxy
        assert test_serverless_options.timeout == 0.8

    def test_serverless_options_with_env_vars(self) -> None:
        os.environ["INSTANA_AGENT_KEY"] = "key1"
        os.environ["INSTANA_ENDPOINT_URL"] = "localhost"
        os.environ["INSTANA_DISABLE_CA_CHECK"] = "true"
        os.environ["INSTANA_ENDPOINT_PROXY"] = "proxy1"
        os.environ["INSTANA_TIMEOUT"] = "3000"
        os.environ["INSTANA_LOG_LEVEL"] = "info"

        test_serverless_options = ServerlessOptions()

        assert test_serverless_options.agent_key == "key1"
        assert test_serverless_options.endpoint_url == "localhost"
        assert not test_serverless_options.ssl_verify
        assert test_serverless_options.endpoint_proxy == {"https": "proxy1"}
        assert test_serverless_options.timeout == 3
        assert test_serverless_options.log_level == logging.INFO


class TestAWSLambdaOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield
        clean_env_vars()

    def test_aws_lambda_options(self) -> None:
        test_aws_lambda_options = AWSLambdaOptions()

        assert not test_aws_lambda_options.agent_key
        assert not test_aws_lambda_options.endpoint_url
        assert test_aws_lambda_options.ssl_verify
        assert not test_aws_lambda_options.endpoint_proxy
        assert test_aws_lambda_options.timeout == 0.8
        assert test_aws_lambda_options.log_level == logging.WARN


class TestAWSFargateOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield
        clean_env_vars()

    def test_aws_fargate_options(self) -> None:
        test_aws_fargate_options = AWSFargateOptions()

        assert not test_aws_fargate_options.agent_key
        assert not test_aws_fargate_options.endpoint_url
        assert test_aws_fargate_options.ssl_verify
        assert not test_aws_fargate_options.endpoint_proxy
        assert test_aws_fargate_options.timeout == 0.8
        assert test_aws_fargate_options.log_level == logging.WARN
        assert not test_aws_fargate_options.tags
        assert not test_aws_fargate_options.zone

    def test_aws_fargate_options_with_env_vars(self) -> None:
        os.environ["INSTANA_AGENT_KEY"] = "key1"
        os.environ["INSTANA_ENDPOINT_URL"] = "localhost"
        os.environ["INSTANA_DISABLE_CA_CHECK"] = "true"
        os.environ["INSTANA_ENDPOINT_PROXY"] = "proxy1"
        os.environ["INSTANA_TIMEOUT"] = "3000"
        os.environ["INSTANA_LOG_LEVEL"] = "info"
        os.environ["INSTANA_TAGS"] = "key1=value1,key2=value2"
        os.environ["INSTANA_ZONE"] = "zone1"

        test_aws_fargate_options = AWSFargateOptions()

        assert test_aws_fargate_options.agent_key == "key1"
        assert test_aws_fargate_options.endpoint_url == "localhost"
        assert not test_aws_fargate_options.ssl_verify
        assert test_aws_fargate_options.endpoint_proxy == {"https": "proxy1"}
        assert test_aws_fargate_options.timeout == 3
        assert test_aws_fargate_options.log_level == logging.INFO

        assert test_aws_fargate_options.tags == {"key1": "value1", "key2": "value2"}
        assert test_aws_fargate_options.zone == "zone1"


class TestEKSFargateOptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield
        clean_env_vars()

    def test_eks_fargate_options(self) -> None:
        test_eks_fargate_options = EKSFargateOptions()

        assert not test_eks_fargate_options.agent_key
        assert not test_eks_fargate_options.endpoint_url
        assert test_eks_fargate_options.ssl_verify
        assert not test_eks_fargate_options.endpoint_proxy
        assert test_eks_fargate_options.timeout == 0.8
        assert test_eks_fargate_options.log_level == logging.WARN

    def test_eks_fargate_options_with_env_vars(self) -> None:
        os.environ["INSTANA_AGENT_KEY"] = "key1"
        os.environ["INSTANA_ENDPOINT_URL"] = "localhost"
        os.environ["INSTANA_DISABLE_CA_CHECK"] = "true"
        os.environ["INSTANA_ENDPOINT_PROXY"] = "proxy1"
        os.environ["INSTANA_TIMEOUT"] = "3000"
        os.environ["INSTANA_LOG_LEVEL"] = "info"

        test_eks_fargate_options = EKSFargateOptions()

        assert test_eks_fargate_options.agent_key == "key1"
        assert test_eks_fargate_options.endpoint_url == "localhost"
        assert not test_eks_fargate_options.ssl_verify
        assert test_eks_fargate_options.endpoint_proxy == {"https": "proxy1"}
        assert test_eks_fargate_options.timeout == 3
        assert test_eks_fargate_options.log_level == logging.INFO


class TestGCROptions:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        yield
        clean_env_vars()

    def test_gcr_options(self) -> None:
        test_gcr_options = GCROptions()

        assert not test_gcr_options.debug
        assert test_gcr_options.log_level == logging.WARN
        assert not test_gcr_options.extra_http_headers
        assert not test_gcr_options.allow_exit_as_root
        assert not test_gcr_options.ignore_endpoints
        assert test_gcr_options.secrets_matcher == "contains-ignore-case"
        assert test_gcr_options.secrets_list == ["key", "pass", "secret"]
        assert not test_gcr_options.secrets
        assert not test_gcr_options.agent_key
        assert not test_gcr_options.endpoint_url
        assert test_gcr_options.ssl_verify
        assert not test_gcr_options.endpoint_proxy
        assert test_gcr_options.timeout == 0.8

    def test_gcr_options_with_env_vars(self) -> None:
        os.environ["INSTANA_AGENT_KEY"] = "key1"
        os.environ["INSTANA_ENDPOINT_URL"] = "localhost"
        os.environ["INSTANA_DISABLE_CA_CHECK"] = "true"
        os.environ["INSTANA_ENDPOINT_PROXY"] = "proxy1"
        os.environ["INSTANA_TIMEOUT"] = "3000"
        os.environ["INSTANA_LOG_LEVEL"] = "info"

        test_gcr_options = GCROptions()

        assert test_gcr_options.agent_key == "key1"
        assert test_gcr_options.endpoint_url == "localhost"
        assert not test_gcr_options.ssl_verify
        assert test_gcr_options.endpoint_proxy == {"https": "proxy1"}
        assert test_gcr_options.timeout == 3
        assert test_gcr_options.log_level == logging.INFO
