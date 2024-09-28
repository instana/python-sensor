# (c) Copyright IBM Corp. 2024

import os
from typing import Generator

import pytest

from instana.agent.aws_eks_fargate import EKSFargateAgent
from instana.singletons import get_agent


class TestEKSFargateCollector:
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
            "INSTANA_ZONE",
            "INSTANA_TAGS",
        )
        for variable_name in variable_names:
            if variable_name in os.environ:
                os.environ.pop(variable_name)

    def test_prepare_payload_basics(self) -> None:
        payload = self.agent.collector.prepare_payload()

        assert payload
        assert len(payload.keys()) == 2
        assert "spans" in payload
        assert isinstance(payload["spans"], list)
        assert len(payload["spans"]) == 0
        assert "metrics" in payload
        assert len(payload["metrics"].keys()) == 1
        assert "plugins" in payload["metrics"]
        assert isinstance(payload["metrics"]["plugins"], list)
        assert len(payload["metrics"]["plugins"]) == 2

        process_plugin = payload["metrics"]["plugins"][0]
        assert "data" in process_plugin

        runtime_plugin = payload["metrics"]["plugins"][1]
        assert "name" in runtime_plugin
        assert "entityId" in runtime_plugin
        assert "data" in runtime_plugin

    def test_no_instana_zone(self) -> None:
        assert not self.agent.options.zone
