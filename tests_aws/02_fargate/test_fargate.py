# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import logging
import os
from typing import Generator

import pytest

from instana.agent.aws_fargate import AWSFargateAgent
from instana.options import AWSFargateOptions
from instana.singletons import get_agent


class TestFargate:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        os.environ["AWS_EXECUTION_ENV"] = "AWS_ECS_FARGATE"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"
        self.agent = AWSFargateAgent()
        yield
        # tearDown
        # Reset all environment variables of consequence
        if "AWS_EXECUTION_ENV" in os.environ:
            os.environ.pop("AWS_EXECUTION_ENV")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_ENDPOINT_PROXY" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_PROXY")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")
        if "INSTANA_LOG_LEVEL" in os.environ:
            os.environ.pop("INSTANA_LOG_LEVEL")
        if "INSTANA_SECRETS" in os.environ:
            os.environ.pop("INSTANA_SECRETS")
        if "INSTANA_DEBUG" in os.environ:
            os.environ.pop("INSTANA_DEBUG")
        if "INSTANA_TAGS" in os.environ:
            os.environ.pop("INSTANA_TAGS")

    def test_has_options(self) -> None:
        assert hasattr(self.agent, "options")
        assert isinstance(self.agent.options, AWSFargateOptions)

    def test_invalid_options(self) -> None:
        # None of the required env vars are available...
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

        agent = AWSFargateAgent()
        assert not agent.can_send()
        assert not agent.collector

    def test_default_secrets(self) -> None:
        assert not self.agent.options.secrets
        assert hasattr(self.agent.options, "secrets_matcher")
        assert self.agent.options.secrets_matcher == "contains-ignore-case"
        assert hasattr(self.agent.options, "secrets_list")
        assert self.agent.options.secrets_list == ["key", "pass", "secret"]

    def test_custom_secrets(self) -> None:
        os.environ["INSTANA_SECRETS"] = "equals:love,war,games"
        agent = AWSFargateAgent()

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
        agent = AWSFargateAgent()
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
        agent = AWSFargateAgent()
        assert agent.options.log_level == logging.ERROR

    def test_custom_proxy(self) -> None:
        os.environ["INSTANA_ENDPOINT_PROXY"] = "http://myproxy.123"
        agent = AWSFargateAgent()
        assert agent.options.endpoint_proxy == {"https": "http://myproxy.123"}
