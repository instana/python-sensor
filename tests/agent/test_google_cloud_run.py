# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import logging
import os
from typing import Generator

import pytest

from instana.agent.google_cloud_run import GCRAgent
from instana.options import GCROptions
from instana.recorder import StanRecorder
from instana.singletons import get_agent, get_tracer, set_agent, set_tracer
from instana.tracer import InstanaTracer, InstanaTracerProvider


class TestGCR:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.agent = None
        self.span_recorder = None
        self.tracer = None

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

        os.environ["K_SERVICE"] = "service"
        os.environ["K_CONFIGURATION"] = "configuration"
        os.environ["K_REVISION"] = "revision"
        os.environ["PORT"] = "port"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"
        yield
        if "K_SERVICE" in os.environ:
            os.environ.pop("K_SERVICE")
        if "K_CONFIGURATION" in os.environ:
            os.environ.pop("K_CONFIGURATION")
        if "K_REVISION" in os.environ:
            os.environ.pop("K_REVISION")
        if "PORT" in os.environ:
            os.environ.pop("PORT")
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

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(
        self, tracer_provider: InstanaTracerProvider
    ) -> None:
        self.agent = GCRAgent(
            service="service",
            configuration="configuration",
            revision="revision",
        )
        self.span_processor = StanRecorder(self.agent)
        self.tracer = InstanaTracer(
            tracer_provider.sampler,
            self.span_processor,
            tracer_provider._exporter,
            tracer_provider._propagators,
        )
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_has_options(self, tracer_provider: InstanaTracerProvider) -> None:
        self.create_agent_and_setup_tracer(tracer_provider=tracer_provider)
        assert hasattr(self.agent, "options")
        assert isinstance(self.agent.options, GCROptions)

    def test_invalid_options(self):
        # None of the required env vars are available...
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

        agent = GCRAgent(
            service="service", configuration="configuration", revision="revision"
        )
        assert not agent.can_send()
        assert not agent.collector

    def test_default_secrets(self, tracer_provider: InstanaTracerProvider) -> None:
        self.create_agent_and_setup_tracer(tracer_provider=tracer_provider)
        assert not self.agent.options.secrets
        assert hasattr(self.agent.options, "secrets_matcher")
        assert self.agent.options.secrets_matcher == "contains-ignore-case"
        assert hasattr(self.agent.options, "secrets_list")
        assert self.agent.options.secrets_list == ["key", "pass", "secret"]

    def test_custom_secrets(self, tracer_provider: InstanaTracerProvider) -> None:
        os.environ["INSTANA_SECRETS"] = "equals:love,war,games"
        self.create_agent_and_setup_tracer(tracer_provider=tracer_provider)

        assert hasattr(self.agent.options, "secrets_matcher")
        assert self.agent.options.secrets_matcher == "equals"
        assert hasattr(self.agent.options, "secrets_list")
        assert self.agent.options.secrets_list == ["love", "war", "games"]

    def test_has_extra_http_headers(
        self, tracer_provider: InstanaTracerProvider
    ) -> None:
        self.create_agent_and_setup_tracer(tracer_provider=tracer_provider)
        assert hasattr(self.agent, "options")
        assert hasattr(self.agent.options, "extra_http_headers")

    def test_agent_extra_http_headers(
        self, tracer_provider: InstanaTracerProvider
    ) -> None:
        os.environ["INSTANA_EXTRA_HTTP_HEADERS"] = (
            "X-Test-Header;X-Another-Header;X-And-Another-Header"
        )
        self.create_agent_and_setup_tracer(tracer_provider=tracer_provider)
        assert self.agent.options.extra_http_headers
        should_headers = ["x-test-header", "x-another-header", "x-and-another-header"]
        assert should_headers == self.agent.options.extra_http_headers

    def test_agent_default_log_level(
        self, tracer_provider: InstanaTracerProvider
    ) -> None:
        self.create_agent_and_setup_tracer(tracer_provider=tracer_provider)
        assert self.agent.options.log_level == logging.WARNING

    def test_agent_custom_log_level(
        self, tracer_provider: InstanaTracerProvider
    ) -> None:
        os.environ["INSTANA_LOG_LEVEL"] = "eRror"
        self.create_agent_and_setup_tracer(tracer_provider=tracer_provider)
        assert self.agent.options.log_level == logging.ERROR

    def test_custom_proxy(self, tracer_provider: InstanaTracerProvider) -> None:
        os.environ["INSTANA_ENDPOINT_PROXY"] = "http://myproxy.123"
        self.create_agent_and_setup_tracer(tracer_provider=tracer_provider)
        assert self.agent.options.endpoint_proxy == {"https": "http://myproxy.123"}
