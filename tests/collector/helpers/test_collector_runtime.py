# (c) Copyright IBM Corp. 2024

from typing import Generator
from unittest.mock import patch

import pytest

from instana.agent.host import HostAgent
from instana.collector.helpers.resource_usage import ResourceUsage
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

    def test_collect_runtime_metrics(self) -> None:
        """Test that _collect_runtime_metrics properly collects metrics"""
        plugin_data = self.helper.collect_metrics()

        # Call the method directly
        self.helper._collect_runtime_metrics(plugin_data[0], True)

        # Verify metrics were collected
        assert "metrics" in plugin_data[0]["data"]
        metrics = plugin_data[0]["data"]["metrics"]

        # Check that resource usage metrics are present
        assert "ru_utime" in metrics
        assert "ru_stime" in metrics
        assert "ru_maxrss" in metrics
        assert "ru_minflt" in metrics
        assert "ru_majflt" in metrics

        # Check that thread metrics are present
        assert "daemon_threads" in metrics
        assert "alive_threads" in metrics
        assert "dummy_threads" in metrics

    def test_runtime_helper_initialization_with_resource_usage(self, mocker):
        """Test that RuntimeHelper initializes with resource_usage"""
        mock_resource = ResourceUsage(
            ru_utime=1.0,
            ru_stime=2.0,
            ru_maxrss=3,
        )
        mocker.patch(
            "instana.collector.helpers.runtime.get_resource_usage",
            return_value=mock_resource,
        )

        helper = RuntimeHelper(collector=HostCollector(HostAgent()))

        assert helper.previous_rusage == mock_resource
        assert helper.previous_rusage.ru_utime == 1.0
        assert helper.previous_rusage.ru_stime == 2.0
        assert helper.previous_rusage.ru_maxrss == 3

    def test_collect_runtime_metrics_with_resource_usage(self, mocker):
        """Test that _collect_runtime_metrics uses resource_usage correctly"""
        # Setup initial state
        initial_resource = ResourceUsage(
            ru_utime=1.0,
            ru_stime=2.0,
            ru_maxrss=3000,
            ru_minflt=100,
            ru_majflt=10,
            ru_nswap=5,
            ru_inblock=200,
            ru_oublock=300,
            ru_msgsnd=10,
            ru_msgrcv=20,
            ru_nsignals=1,
            ru_nvcsw=1000,
            ru_nivcsw=500,
        )
        self.helper.previous_rusage = initial_resource

        # Setup new resource usage values with increments
        new_resource = ResourceUsage(
            ru_utime=1.5,  # +0.5
            ru_stime=3.0,  # +1.0
            ru_maxrss=4000,  # +1000
            ru_minflt=150,  # +50
            ru_majflt=15,  # +5
            ru_nswap=7,  # +2
            ru_inblock=250,  # +50
            ru_oublock=350,  # +50
            ru_msgsnd=15,  # +5
            ru_msgrcv=25,  # +5
            ru_nsignals=3,  # +2
            ru_nvcsw=1200,  # +200
            ru_nivcsw=600,  # +100
        )
        mocker.patch(
            "instana.collector.helpers.runtime.get_resource_usage",
            return_value=new_resource,
        )

        # Call the method
        plugin_data = {"data": {"metrics": {}}}
        self.helper._collect_runtime_metrics(plugin_data, True)

        # Verify metrics were collected with correct deltas
        metrics = plugin_data["data"]["metrics"]
        assert metrics["ru_utime"] == 0.5  # Difference between new and old
        assert metrics["ru_stime"] == 1.0
        assert metrics["ru_maxrss"] == 4000  # This is absolute, not a delta
        assert metrics["ru_minflt"] == 50
        assert metrics["ru_majflt"] == 5
        assert metrics["ru_nswap"] == 2
        assert metrics["ru_inblock"] == 50
        assert metrics["ru_oublock"] == 50
        assert metrics["ru_msgsnd"] == 5
        assert metrics["ru_msgrcv"] == 5
        assert metrics["ru_nsignals"] == 2
        assert metrics["ru_nvcsw"] == 200
        assert metrics["ru_nivcsw"] == 100

        # Verify the previous_rusage was updated
        assert self.helper.previous_rusage == new_resource

    @patch("os.environ")
    def test_collect_runtime_metrics_disabled(self, mock_environ):
        """Test that _collect_runtime_metrics respects INSTANA_DISABLE_METRICS_COLLECTION"""
        # Setup environment variable
        mock_environ.get.return_value = True

        # Call the method
        plugin_data = {"data": {"metrics": {}}}
        self.helper._collect_runtime_metrics(plugin_data, True)

        # Verify no metrics were collected
        assert plugin_data["data"]["metrics"] == {}
