# (c) Copyright IBM Corp. 2024

import logging
import os
from typing import Generator

import pytest

from instana.agent.aws_eks_fargate import EKSFargateAgent
from instana.options import EKSFargateOptions
from instana.singletons import get_agent


class TestEKSFargate:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        os.environ["INSTANA_TRACER_ENVIRONMENT"] = "AWS_EKS_FARGATE"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"
        self.agent = EKSFargateAgent()
        yield
        # tearDown
        # Reset all environment variables of consequence
        variable_names = (
            "INSTANA_TRACER_ENVIRONMENT",
            "AWS_EXECUTION_ENV",
            "INSTANA_EXTRA_HTTP_HEADERS",
            "INSTANA_ENDPOINT_URL",
            "INSTANA_ENDPOINT_PROXY",
            "INSTANA_AGENT_KEY",
            "INSTANA_LOG_LEVEL",
            "INSTANA_SECRETS",
            "INSTANA_DEBUG",
            "INSTANA_TAGS",
        )

        for variable_name in variable_names:
            if variable_name in os.environ:
                os.environ.pop(variable_name)

    def test_has_options(self) -> None:
        assert hasattr(self.agent, "options")
        assert isinstance(self.agent.options, EKSFargateOptions)

    def test_missing_variables(self, caplog) -> None:
        os.environ.pop("INSTANA_ENDPOINT_URL")
        agent = EKSFargateAgent()
        assert not agent.can_send()
        assert not agent.collector
        assert (
            "Required INSTANA_AGENT_KEY and/or INSTANA_ENDPOINT_URL environment variables not set.  We will not be able to monitor this Pod."
            in caplog.messages
        )

        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ.pop("INSTANA_AGENT_KEY")
        agent = EKSFargateAgent()
        assert not agent.can_send()
        assert not agent.collector
        assert (
            "Required INSTANA_AGENT_KEY and/or INSTANA_ENDPOINT_URL environment variables not set.  We will not be able to monitor this Pod."
            in caplog.messages
        )

    def test_default_secrets(self) -> None:
        assert not self.agent.options.secrets
        assert hasattr(self.agent.options, "secrets_matcher")
        assert self.agent.options.secrets_matcher == "contains-ignore-case"
        assert hasattr(self.agent.options, "secrets_list")
        assert self.agent.options.secrets_list == ["key", "pass", "secret"]

    def test_custom_secrets(self) -> None:
        os.environ["INSTANA_SECRETS"] = "equals:love,war,games"
        agent = EKSFargateAgent()

        assert hasattr(agent.options, "secrets_matcher")
        assert agent.options.secrets_matcher == "equals"
        assert hasattr(agent.options, "secrets_list")
        assert agent.options.secrets_list == ["love", "war", "games"]

    def test_default_tags(self) -> None:
        assert hasattr(self.agent.options, "tags")
        assert not self.agent.options.tags

    def test_has_extra_http_headers(self) -> None:
        assert hasattr(self.agent, "options")
        assert hasattr(self.agent.options, "extra_http_headers")

    def test_agent_extra_http_headers(self) -> None:
        os.environ["INSTANA_EXTRA_HTTP_HEADERS"] = (
            "X-Test-Header;X-Another-Header;X-And-Another-Header"
        )
        agent = EKSFargateAgent()
        assert agent.options.extra_http_headers
        assert agent.options.extra_http_headers == [
            "x-test-header",
            "x-another-header",
            "x-and-another-header",
        ]

    def test_agent_default_log_level(self) -> None:
        assert self.agent.options.log_level == logging.WARNING

    def test_agent_custom_log_level(self) -> None:
        os.environ["INSTANA_LOG_LEVEL"] = "eRror"
        agent = EKSFargateAgent()
        assert agent.options.log_level == logging.ERROR

    def test_custom_proxy(self) -> None:
        os.environ["INSTANA_ENDPOINT_PROXY"] = "http://myproxy.123"
        agent = EKSFargateAgent()
        assert agent.options.endpoint_proxy == {"https": "http://myproxy.123"}
