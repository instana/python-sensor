# (c) Copyright IBM Corp. 2024

from collections.abc import Generator
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
        assert helper.previous_gc_stats is None

    def test_collect_metrics(self) -> None:
        response = self.helper.collect_metrics()
        assert response[0]["name"] == "com.instana.plugin.python"

    def test_collect_runtime_snapshot_default(self) -> None:
        plugin_data = self.helper.collect_metrics()
        self.helper._collect_runtime_snapshot(plugin_data[0])
        assert plugin_data[0]["name"] == "com.instana.plugin.python"
        assert plugin_data[0]["data"]["snapshot"]["m"] == "Manual"
        # data contains: pid, metrics, pollRate, snapshot
        # pollRate is now written by collect_metrics() on every poll, not by _collect_runtime_snapshot()
        assert len(plugin_data[0]["data"]) == 4

    def test_collect_runtime_snapshot_autowrapt(self) -> None:
        with patch(
            "instana.collector.helpers.runtime.is_autowrapt_instrumented",
            return_value=True,
        ):
            plugin_data = self.helper.collect_metrics()
            self.helper._collect_runtime_snapshot(plugin_data[0])
            assert plugin_data[0]["name"] == "com.instana.plugin.python"
            assert plugin_data[0]["data"]["snapshot"]["m"] == "Autowrapt"
            # data contains: pid, metrics, pollRate, snapshot
            # pollRate is now written by collect_metrics() on every poll
            assert len(plugin_data[0]["data"]) == 4

    def test_collect_runtime_snapshot_webhook(self) -> None:
        with patch(
            "instana.collector.helpers.runtime.is_webhook_instrumented",
            return_value=True,
        ):
            plugin_data = self.helper.collect_metrics()
            self.helper._collect_runtime_snapshot(plugin_data[0])
            assert plugin_data[0]["name"] == "com.instana.plugin.python"
            assert plugin_data[0]["data"]["snapshot"]["m"] == "AutoTrace"
            # data contains: pid, metrics, pollRate, snapshot
            # pollRate is now written by collect_metrics() on every poll
            assert len(plugin_data[0]["data"]) == 4

    def test_collect_gc_metrics(self) -> None:
        plugin_data = self.helper.collect_metrics()

        # First call establishes the baseline (previous_gc_stats was None); no
        # data is written yet.
        self.helper._collect_gc_metrics(plugin_data[0], True)
        assert self.helper.previous_gc_stats is not None

        # Second call computes deltas from the baseline and writes them into plugin_data.
        # All 9 keys (collections/collected/uncollectable × gen0/1/2) are always written
        # so that filler receives a signal every poll and does not zero-fill on quiet periods.
        self.helper._collect_gc_metrics(plugin_data[0], True)
        gc_metrics = plugin_data[0]["data"]["metrics"]["gc"]
        expected_keys = [
            f"{k}{i}"
            for k in ("collections", "collected", "uncollectable")
            for i in range(3)
        ]
        for key in expected_keys:
            assert key in gc_metrics, f"{key} must always be present in GC metrics"

    def test_collect_gc_metrics_reports_delta_between_polls(self) -> None:
        """GC metrics must be deltas between successive polls, not kumulatif values."""
        # Simulate first poll: previous_gc_stats set to known baseline
        baseline = [
            {"collections": 100, "collected": 200, "uncollectable": 0},
            {"collections": 10, "collected": 50, "uncollectable": 0},
            {"collections": 1, "collected": 5, "uncollectable": 0},
        ]
        self.helper.previous_gc_stats = baseline

        # Simulate gc.get_stats() returning incremented counts
        after = [
            {"collections": 103, "collected": 206, "uncollectable": 0},
            {"collections": 11, "collected": 53, "uncollectable": 0},
            {"collections": 1, "collected": 5, "uncollectable": 0},
        ]

        plugin_data = [{"data": {"metrics": {"gc": {}}}}]

        with patch("gc.get_stats", return_value=after):
            self.helper._collect_gc_metrics(plugin_data[0], True)

        gc_metrics = plugin_data[0]["data"]["metrics"]["gc"]
        # Gen 0: collections delta = 3, collected delta = 6, uncollectable delta = 0
        assert gc_metrics["collections0"] == 3
        assert gc_metrics["collected0"] == 6
        assert gc_metrics["uncollectable0"] == 0   # delta=0 is now always sent
        # Gen 1: collections delta = 1, collected delta = 3, uncollectable delta = 0
        assert gc_metrics["collections1"] == 1
        assert gc_metrics["collected1"] == 3
        assert gc_metrics["uncollectable1"] == 0   # delta=0 is now always sent
        # Gen 2: no change — all deltas = 0, but still sent
        assert gc_metrics["collections2"] == 0
        assert gc_metrics["collected2"] == 0
        assert gc_metrics["uncollectable2"] == 0

        # previous_gc_stats must be updated to the latest snapshot
        assert self.helper.previous_gc_stats == after

    def test_collect_gc_metrics_zero_delta_always_sent(self) -> None:
        """delta=0 must always be sent so filler does not zero-fill on quiet GC periods."""
        same = [
            {"collections": 50, "collected": 100, "uncollectable": 0},
            {"collections": 5, "collected": 20, "uncollectable": 0},
            {"collections": 0, "collected": 0, "uncollectable": 0},
        ]
        self.helper.previous_gc_stats = same

        plugin_data = [{"data": {"metrics": {"gc": {}}}}]

        with patch("gc.get_stats", return_value=same):
            self.helper._collect_gc_metrics(plugin_data[0], False)

        gc_metrics = plugin_data[0]["data"]["metrics"]["gc"]
        # All 9 keys must be present, all with value 0
        expected_keys = [
            f"{k}{i}"
            for k in ("collections", "collected", "uncollectable")
            for i in range(3)
        ]
        for key in expected_keys:
            assert key in gc_metrics, f"{key} must be present even with delta=0"
            assert gc_metrics[key] == 0, f"{key} delta must be 0"

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

    def test_collect_metrics_poll_rate_default(self) -> None:
        """pollRate defaults to 1 when agent has no options configured.
        pollRate is now written by collect_metrics() on every poll so that
        filler learns the rate immediately, not just every 5 min via snapshot.
        """
        plugin_data = self.helper.collect_metrics()
        assert plugin_data[0]["data"]["pollRate"] == 1

    def test_collect_metrics_poll_rate_from_agent_options(self) -> None:
        """pollRate is read from agent.options.poll_rate on every collect_metrics() call."""
        self.helper.collector.agent.options.poll_rate = 60
        plugin_data = self.helper.collect_metrics()
        assert plugin_data[0]["data"]["pollRate"] == 60

    def test_collect_metrics_poll_rate_no_options(self) -> None:
        """pollRate defaults to 1 when agent has no options attribute."""
        self.helper.collector.agent.options = None
        plugin_data = self.helper.collect_metrics()
        assert plugin_data[0]["data"]["pollRate"] == 1

    def test_collect_metrics_poll_rate_no_agent(self) -> None:
        """pollRate defaults to 1 when collector has no agent attribute."""
        self.helper.collector.agent = None
        plugin_data = self.helper.collect_metrics()
        assert plugin_data[0]["data"]["pollRate"] == 1

    def test_collect_metrics_poll_rate_at_top_level_not_in_snapshot(self) -> None:
        """pollRate must be at data top-level, not nested inside snapshot.
        Backend's PollRateUtil.regularPollRateFromPayload() reads payload.getByPath("pollRate")
        which is a flat lookup on the data map — it cannot find a nested key.
        """
        self.helper.collector.agent.options.poll_rate = 30
        plugin_data = self.helper.collect_metrics()
        self.helper._collect_runtime_snapshot(plugin_data[0])
        assert plugin_data[0]["data"]["pollRate"] == 30
        assert "pollRate" not in plugin_data[0]["data"].get("snapshot", {})

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
