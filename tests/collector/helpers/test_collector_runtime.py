# (c) Copyright IBM Corp. 2024

from typing import Generator
from unittest.mock import patch

import pytest

from instana.agent.host import HostAgent
from instana.collector.helpers.runtime import RuntimeHelper
from instana.collector.host import HostCollector


class TestRuntimeHelper:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.helper = RuntimeHelper(
            collector=HostCollector(
                HostAgent(),
            ),
        )
        yield
        self.helper = None

    def test_default_while_gc_disabled(self) -> None:
        import gc

        gc.disable()
        helper = RuntimeHelper(collector=HostCollector(HostAgent()))
        assert helper.previous_gc_count is None

    def test_collect_metrics(self) -> None:
        response = self.helper.collect_metrics()
        assert response[0]["name"] == "com.instana.plugin.python"

    def test_collect_runtime_snapshot_default(self) -> None:
        plugin_data = self.helper.collect_metrics()
        self.helper._collect_runtime_snapshot(plugin_data[0])
        assert plugin_data[0]["name"] == "com.instana.plugin.python"
        assert plugin_data[0]["data"]["snapshot"]["m"] == "Manual"
        assert len(plugin_data[0]["data"]) == 3

    def test_collect_runtime_snapshot_autowrapt(self) -> None:
        with patch(
            "instana.collector.helpers.runtime.is_autowrapt_instrumented",
            return_value=True,
        ):
            plugin_data = self.helper.collect_metrics()
            self.helper._collect_runtime_snapshot(plugin_data[0])
            assert plugin_data[0]["name"] == "com.instana.plugin.python"
            assert plugin_data[0]["data"]["snapshot"]["m"] == "Autowrapt"
            assert len(plugin_data[0]["data"]) == 3

    def test_collect_runtime_snapshot_webhook(self) -> None:
        with patch(
            "instana.collector.helpers.runtime.is_webhook_instrumented",
            return_value=True,
        ):
            plugin_data = self.helper.collect_metrics()
            self.helper._collect_runtime_snapshot(plugin_data[0])
            assert plugin_data[0]["name"] == "com.instana.plugin.python"
            assert plugin_data[0]["data"]["snapshot"]["m"] == "AutoTrace"
            assert len(plugin_data[0]["data"]) == 3

    def test_collect_gc_metrics(self) -> None:
        plugin_data = self.helper.collect_metrics()

        self.helper._collect_gc_metrics(plugin_data[0], True)
        assert len(self.helper.previous["data"]["metrics"]["gc"]) == 6
