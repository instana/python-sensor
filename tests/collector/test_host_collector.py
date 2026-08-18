# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import gc
import logging
import os
import sys
import threading
from collections.abc import Generator

import pytest
from mock import patch
from pytest import LogCaptureFixture

from instana.collector.helpers.runtime import (
    PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR,
)
from instana.collector.host import HostCollector
from instana.singletons import get_agent, get_tracer
from instana.version import VERSION


class TestHostCollector:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.agent = get_agent()
        self.agent.collector = HostCollector(self.agent)
        self.tracer = get_tracer()
        self.webhook_sitedir_path = PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR + "3.8.0"
        self.payload = None
        yield
        self.agent.collector.shutdown(report_final=False)
        variable_names = (
            "AWS_EXECUTION_ENV",
            "INSTANA_EXTRA_HTTP_HEADERS",
            "INSTANA_ENDPOINT_URL",
            "INSTANA_AGENT_KEY",
            "INSTANA_ZONE",
            "INSTANA_TAGS",
            "INSTANA_DISABLE_METRICS_COLLECTION",
            "INSTANA_DISABLE_PYTHON_PACKAGE_COLLECTION",
            "AUTOWRAPT_BOOTSTRAP",
        )

        for variable_name in variable_names:
            if variable_name in os.environ:
                os.environ.pop(variable_name)

        if self.webhook_sitedir_path in sys.path:
            sys.path.remove(self.webhook_sitedir_path)

    def test_start(self) -> None:
        with patch(
            "instana.collector.base.BaseCollector.is_reporting_thread_running",
            return_value=False,
        ):
            self.agent.collector.start()
            assert self.agent.collector.started
            assert self.agent.collector.THREAD_NAME == "Instana Collector"
            assert self.agent.collector.snapshot_data_interval == 300
            assert self.agent.collector.snapshot_data_last_sent == 0
            assert isinstance(self.agent.collector.helpers[0].collector, HostCollector)
            assert len(self.agent.collector.helpers) == 1
            assert isinstance(self.agent.collector.reporting_thread, threading.Thread)
            self.agent.collector.ready_to_start = False
            assert not self.agent.collector.start()

    def test_prepare_and_report_data(self, caplog: LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        self.agent.collector.agent.machine.fsm.current = "wait4init"
        with patch("instana.agent.host.HostAgent.is_agent_ready", return_value=True):
            self.agent.collector.prepare_and_report_data()
            assert "Agent is ready.  Getting to work." in caplog.messages
            assert "Harmless state machine thread disagreement.  Will self-correct on next timer cycle."
        self.agent.collector.agent.machine.fsm.current = "wait4init"
        with patch("instana.agent.host.HostAgent.is_agent_ready", return_value=False):
            assert not self.agent.collector.prepare_and_report_data()
        self.agent.collector.agent.machine.fsm.current = "good2go"
        caplog.clear()
        with patch("instana.agent.host.HostAgent.is_timed_out", return_value=True):
            self.agent.collector.prepare_and_report_data()
            assert (
                "The Instana host agent has gone offline or is no longer reachable for > 1 min.  Will retry periodically."
                in caplog.messages
            )

    def test_should_send_snapshot_data(self) -> None:
        self.agent.collector.snapshot_data_interval = 999999999999
        assert not self.agent.collector.should_send_snapshot_data()

    def test_should_send_metrics_with_default_poll_rate(self) -> None:
        """Test that metrics should be sent immediately with default poll_rate of 1 second"""
        # Initially, metrics_data_last_sent is 0, so should return True
        assert self.agent.collector.should_send_metrics()

        # After updating timestamp, should return False immediately
        from time import time

        self.agent.collector.metrics_data_last_sent = int(time())
        assert not self.agent.collector.should_send_metrics()

    def test_should_send_metrics_with_custom_poll_rate(self) -> None:
        """Test that metrics respect custom poll_rate from agent options"""
        from time import time

        from instana.options import StandardOptions

        # Set custom poll_rate of 5 seconds
        self.agent.options = StandardOptions()
        self.agent.options.poll_rate = 5

        # Initially should return True
        assert self.agent.collector.should_send_metrics()

        # Set timestamp to now
        current_time = int(time())
        self.agent.collector.metrics_data_last_sent = current_time

        # Should return False immediately after
        assert not self.agent.collector.should_send_metrics()

        # Simulate 3 seconds passing (less than poll_rate)
        self.agent.collector.metrics_data_last_sent = current_time - 3
        assert not self.agent.collector.should_send_metrics()

        # Simulate 5 seconds passing (equal to poll_rate)
        self.agent.collector.metrics_data_last_sent = current_time - 5
        assert self.agent.collector.should_send_metrics()

        # Simulate 6 seconds passing (more than poll_rate)
        self.agent.collector.metrics_data_last_sent = current_time - 6
        assert self.agent.collector.should_send_metrics()

    def test_should_send_metrics_without_agent_options(self) -> None:
        """Test that should_send_metrics works when agent has no options attribute"""
        from time import time

        # Remove options attribute to test fallback
        if hasattr(self.agent, "options"):
            delattr(self.agent, "options")

        # Should use default poll_rate of 1
        assert self.agent.collector.should_send_metrics()

        self.agent.collector.metrics_data_last_sent = int(time())
        assert not self.agent.collector.should_send_metrics()

    def test_prepare_payload_respects_poll_rate(self) -> None:
        """Test that prepare_payload only collects metrics based on poll_rate"""
        from time import time

        from instana.options import StandardOptions

        # Set poll_rate to 5 seconds
        self.agent.options = StandardOptions()
        self.agent.options.poll_rate = 5

        with patch.object(gc, "isenabled", return_value=True):
            # First call should collect metrics
            self.agent.collector.metrics_data_last_sent = 0
            payload = self.agent.collector.prepare_payload()
            assert payload
            assert "metrics" in payload
            assert "plugins" in payload["metrics"]
            assert len(payload["metrics"]["plugins"]) == 1

            # Immediately after, should not collect metrics (empty plugins)
            payload = self.agent.collector.prepare_payload()
            assert payload
            assert "metrics" in payload
            assert "plugins" in payload["metrics"]
            assert len(payload["metrics"]["plugins"]) == 0

            # Simulate 5 seconds passing
            self.agent.collector.metrics_data_last_sent = int(time()) - 5
            payload = self.agent.collector.prepare_payload()
            assert payload
            assert "metrics" in payload
            assert "plugins" in payload["metrics"]
            assert len(payload["metrics"]["plugins"]) == 1

    def test_metrics_data_last_sent_updated(self) -> None:
        """Test that metrics_data_last_sent timestamp is updated after collecting metrics"""
        from time import time

        from instana.options import StandardOptions

        self.agent.options = StandardOptions()
        self.agent.options.poll_rate = 1

        with patch.object(gc, "isenabled", return_value=True):
            # Reset timestamp
            self.agent.collector.metrics_data_last_sent = 0
            initial_time = int(time())

            # Prepare payload should update timestamp
            payload = self.agent.collector.prepare_payload()
            assert payload

            # Verify timestamp was updated
            assert self.agent.collector.metrics_data_last_sent >= initial_time
            assert self.agent.collector.metrics_data_last_sent <= int(time())

    def test_prepare_payload_spans_always_collected(self) -> None:
        """Test that spans are always collected regardless of poll_rate"""
        from instana.options import StandardOptions
        from instana.recorder import StanRecorder
        from instana.span.registered_span import RegisteredSpan
        from instana.span.span import InstanaSpan
        from instana.span_context import SpanContext

        # Set high poll_rate
        self.agent.options = StandardOptions()
        self.agent.options.poll_rate = 5

        with patch.object(gc, "isenabled", return_value=True):
            # Create span context and processor
            span_context = SpanContext(trace_id=123, span_id=456, is_remote=False)
            span_processor = StanRecorder(self.agent)

            # Add a span to the queue
            span = InstanaSpan("test-span", span_context, span_processor)
            registered_span = RegisteredSpan(span, None, "log")
            self.agent.collector.span_queue.put(registered_span)

            # Set metrics_data_last_sent to now (so metrics won't be collected)
            from time import time

            self.agent.collector.metrics_data_last_sent = int(time())

            # Prepare payload
            payload = self.agent.collector.prepare_payload()

            # Spans should still be collected
            assert payload
            assert "spans" in payload
            assert len(payload["spans"]) == 1

            # But metrics should not be collected
            assert "metrics" in payload
            assert "plugins" in payload["metrics"]
            assert len(payload["metrics"]["plugins"]) == 0

    def test_prepare_payload_basics(self) -> None:
        with patch.object(gc, "isenabled", return_value=True):
            # First call establishes the GC baseline; no gc metrics in payload yet.
            self.payload = self.agent.collector.prepare_payload()
            assert self.payload

            assert len(self.payload.keys()) == 3
            assert "spans" in self.payload
            assert isinstance(self.payload["spans"], list)
            assert len(self.payload["spans"]) == 0
            assert "metrics", self.payload
            assert len(self.payload["metrics"].keys()) == 1
            assert "plugins", self.payload["metrics"]
            assert isinstance(self.payload["metrics"]["plugins"], list)
            assert len(self.payload["metrics"]["plugins"]) == 1

            python_plugin = self.payload["metrics"]["plugins"][0]
            assert python_plugin["name"] == "com.instana.plugin.python"
            assert python_plugin["entityId"] == str(os.getpid())
            assert "data" in python_plugin
            assert "snapshot" in python_plugin["data"]
            assert "m" in python_plugin["data"]["snapshot"]
            assert python_plugin["data"]["snapshot"]["m"] == "Manual"
            assert "metrics" in python_plugin["data"]

            assert "ru_utime" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_utime"]) in [float, int]
            assert "ru_stime" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_stime"]) in [float, int]
            assert "ru_maxrss" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_maxrss"]) in [float, int]
            assert "ru_ixrss" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_ixrss"]) in [float, int]
            assert "ru_idrss" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_idrss"]) in [float, int]
            assert "ru_isrss" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_isrss"]) in [float, int]
            assert "ru_minflt" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_minflt"]) in [float, int]
            assert "ru_majflt" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_majflt"]) in [float, int]
            assert "ru_nswap" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_nswap"]) in [float, int]
            assert "ru_inblock" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_inblock"]) in [float, int]
            assert "ru_oublock" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_oublock"]) in [float, int]
            assert "ru_msgsnd" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_msgsnd"]) in [float, int]
            assert "ru_msgrcv" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_msgrcv"]) in [float, int]
            assert "ru_nsignals" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_nsignals"]) in [float, int]
            assert "ru_nvcsw" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_nvcsw"]) in [float, int]
            assert "ru_nivcsw" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["ru_nivcsw"]) in [float, int]
            assert "alive_threads" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["alive_threads"]) in [
                float,
                int,
            ]
            assert "dummy_threads" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["dummy_threads"]) in [
                float,
                int,
            ]
            assert "daemon_threads" in python_plugin["data"]["metrics"]
            assert type(python_plugin["data"]["metrics"]["daemon_threads"]) in [
                float,
                int,
            ]

            # Second call: GC baseline is now set, so deltas are reported.
            # Reset both timestamps so metrics AND snapshot are collected.
            self.agent.collector.metrics_data_last_sent = 0
            self.agent.collector.snapshot_data_last_sent = 0
            self.payload = self.agent.collector.prepare_payload()
            python_plugin = self.payload["metrics"]["plugins"][0]
            assert "gc" in python_plugin["data"]["metrics"]
            assert isinstance(python_plugin["data"]["metrics"]["gc"], dict)
            for i in range(3):
                for key in ("collections", "collected", "uncollectable"):
                    metric_key = f"{key}{i}"
                    assert metric_key in python_plugin["data"]["metrics"]["gc"]
                    assert type(python_plugin["data"]["metrics"]["gc"][metric_key]) in [
                        float,
                        int,
                    ]

    def test_prepare_payload_basics_disable_runtime_metrics(self) -> None:
        os.environ["INSTANA_DISABLE_METRICS_COLLECTION"] = "TRUE"
        self.payload = self.agent.collector.prepare_payload()
        assert self.payload

        assert len(self.payload.keys()) == 3
        assert "spans" in self.payload
        assert isinstance(self.payload["spans"], list)
        assert len(self.payload["spans"]) == 0
        assert "metrics" in self.payload
        assert len(self.payload["metrics"].keys()) == 1
        assert "plugins" in self.payload["metrics"]
        assert isinstance(self.payload["metrics"]["plugins"], list)
        assert len(self.payload["metrics"]["plugins"]) == 1

        python_plugin = self.payload["metrics"]["plugins"][0]
        assert python_plugin["name"] == "com.instana.plugin.python"
        assert python_plugin["entityId"] == str(os.getpid())
        assert "data" in python_plugin
        assert "snapshot" in python_plugin["data"]
        assert "m" in python_plugin["data"]["snapshot"]
        assert python_plugin["data"]["snapshot"]["m"] == "Manual"
        assert "metrics" not in python_plugin["data"]

    def test_prepare_payload_with_snapshot_with_python_packages(self) -> None:
        self.payload = self.agent.collector.prepare_payload()
        assert self.payload
        assert "snapshot" in self.payload["metrics"]["plugins"][0]["data"]
        snapshot = self.payload["metrics"]["plugins"][0]["data"]["snapshot"]
        assert snapshot
        assert "m" in snapshot
        assert snapshot["m"] == "Manual"
        assert "version" in snapshot
        assert len(snapshot["versions"]) > 5
        assert snapshot["versions"]["instana"] == VERSION
        assert "wrapt" in snapshot["versions"]
        assert "fysom" in snapshot["versions"]

    def test_prepare_payload_with_snapshot_disabled_python_packages(self) -> None:
        os.environ["INSTANA_DISABLE_PYTHON_PACKAGE_COLLECTION"] = "TRUE"
        self.payload = self.agent.collector.prepare_payload()
        assert self.payload
        assert "snapshot" in self.payload["metrics"]["plugins"][0]["data"]
        snapshot = self.payload["metrics"]["plugins"][0]["data"]["snapshot"]
        assert snapshot
        assert "m" in snapshot
        assert snapshot["m"] == "Manual"
        assert "version" in snapshot
        assert len(snapshot["versions"]) == 1
        assert snapshot["versions"]["instana"] == VERSION

    def test_prepare_payload_with_autowrapt(self) -> None:
        os.environ["AUTOWRAPT_BOOTSTRAP"] = "instana"
        self.payload = self.agent.collector.prepare_payload()
        assert self.payload
        assert "snapshot" in self.payload["metrics"]["plugins"][0]["data"]
        snapshot = self.payload["metrics"]["plugins"][0]["data"]["snapshot"]
        assert snapshot
        assert "m" in snapshot
        assert snapshot["m"] == "Autowrapt"
        assert "version" in snapshot
        assert len(snapshot["versions"]) > 5
        expected_packages = ("instana", "wrapt", "fysom")
        for package in expected_packages:
            assert (
                package in snapshot["versions"]
            ), f"{package} not found in snapshot['versions']"
        assert snapshot["versions"]["instana"] == VERSION

    def test_prepare_payload_with_autotrace(self) -> None:
        sys.path.append(self.webhook_sitedir_path)
        self.payload = self.agent.collector.prepare_payload()
        assert self.payload
        assert "snapshot" in self.payload["metrics"]["plugins"][0]["data"]
        snapshot = self.payload["metrics"]["plugins"][0]["data"]["snapshot"]
        assert snapshot
        assert "m" in snapshot
        assert snapshot["m"] == "AutoTrace"
        assert "version" in snapshot
        assert len(snapshot["versions"]) > 5
        expected_packages = ("instana", "wrapt", "fysom")
        for package in expected_packages:
            assert (
                package in snapshot["versions"]
            ), f"{package} not found in snapshot['versions']"
        assert snapshot["versions"]["instana"] == VERSION

    def test_prepare_and_report_data_without_lock(
        self, caplog: LogCaptureFixture
    ) -> None:
        """Test prepare_and_report_data when machine._lock is missing."""
        caplog.set_level(logging.DEBUG, logger="instana")

        # Remove the _lock attribute to simulate older code or edge cases
        if hasattr(self.agent.machine, "_lock"):
            delattr(self.agent.machine, "_lock")

        self.agent.collector.agent.machine.fsm.current = "wait4init"

        with patch("instana.agent.host.HostAgent.is_agent_ready", return_value=True):
            # Should handle missing lock gracefully and log the harmless disagreement
            self.agent.collector.prepare_and_report_data()
            assert (
                "Harmless state machine thread disagreement.  Will self-correct on next timer cycle."
                in caplog.messages
            )

    def test_prepare_and_report_data_lock_acquisition_wait4init(
        self, caplog: LogCaptureFixture
    ) -> None:
        """Test prepare_and_report_data with lock during wait4init state."""
        caplog.set_level(logging.DEBUG, logger="instana")

        # Ensure lock exists
        import threading

        if not hasattr(self.agent.machine, "_lock"):
            self.agent.machine._lock = threading.RLock()

        self.agent.collector.agent.machine.fsm.current = "wait4init"

        with patch("instana.agent.host.HostAgent.is_agent_ready", return_value=True):
            self.agent.collector.prepare_and_report_data()
            assert "Agent is ready.  Getting to work." in caplog.messages

    def test_prepare_and_report_data_lock_acquisition_good2go(
        self, caplog: LogCaptureFixture
    ) -> None:
        """Test prepare_and_report_data with lock during good2go state."""
        caplog.set_level(logging.DEBUG, logger="instana")

        # Ensure lock exists
        import threading

        if not hasattr(self.agent.machine, "_lock"):
            self.agent.machine._lock = threading.RLock()

        self.agent.collector.agent.machine.fsm.current = "good2go"

        with patch("instana.agent.host.HostAgent.is_timed_out", return_value=True):
            self.agent.collector.prepare_and_report_data()
            assert (
                "The Instana host agent has gone offline or is no longer reachable for > 1 min.  Will retry periodically."
                in caplog.messages
            )

    def test_prepare_and_report_data_concurrent_state_change(
        self, caplog: LogCaptureFixture
    ) -> None:
        """Test prepare_and_report_data when state changes between lock acquisitions."""
        caplog.set_level(logging.DEBUG, logger="instana")

        # Ensure lock exists
        import threading

        if not hasattr(self.agent.machine, "_lock"):
            self.agent.machine._lock = threading.RLock()

        # Start in wait4init
        self.agent.collector.agent.machine.fsm.current = "wait4init"

        # Mock is_agent_ready to change state during execution
        call_count = [0]

        def mock_is_agent_ready():
            call_count[0] += 1
            # Change state after first check to simulate concurrent modification
            if call_count[0] == 1:
                self.agent.collector.agent.machine.fsm.current = "good2go"
            return True

        with patch(
            "instana.agent.host.HostAgent.is_agent_ready",
            side_effect=mock_is_agent_ready,
        ):
            # Should handle state change gracefully
            self.agent.collector.prepare_and_report_data()
            # The second lock acquisition should see the new state
            assert self.agent.collector.agent.machine.fsm.current == "good2go"


class TestHostAgentHeartbeat:
    """Tests for _send_heartbeat() and related poll_rate-aware timeout logic."""

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        from instana.collector.host import HostCollector
        from instana.singletons import get_agent

        self.agent = get_agent()
        self.agent.collector = HostCollector(self.agent)
        yield
        self.agent.collector.shutdown(report_final=False)

    # ------------------------------------------------------------------
    # _send_heartbeat
    # ------------------------------------------------------------------

    def test_heartbeat_updates_last_seen_on_success(self) -> None:
        """HEAD 200 → last_seen must be updated."""
        from unittest.mock import MagicMock

        from instana.agent.host import AnnounceData

        self.agent.announce_data = AnnounceData(pid=12345, agent_uuid="uuid-1")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(self.agent.machine.fsm, "current", "good2go"), \
             patch.object(self.agent.client, "head", return_value=mock_response):
            self.agent._send_heartbeat()

        assert self.agent.last_seen is not None

    def test_heartbeat_skipped_when_announce_data_is_none(self) -> None:
        """announce_data=None (pre-announce) → HEAD must NOT be called."""
        self.agent.announce_data = None
        self.agent.last_seen = None

        with patch.object(self.agent.client, "head") as mock_head:
            self.agent._send_heartbeat()
            mock_head.assert_not_called()

        assert self.agent.last_seen is None

    def test_heartbeat_skipped_when_not_in_good2go_state(self) -> None:
        """FSM state != good2go (e.g. wait4init) → HEAD must NOT be called."""
        from instana.agent.host import AnnounceData

        self.agent.announce_data = AnnounceData(pid=12345, agent_uuid="uuid-1")
        self.agent.last_seen = None
        self.agent.machine.fsm.current = "wait4init"

        with patch.object(self.agent.client, "head") as mock_head:
            self.agent._send_heartbeat()
            mock_head.assert_not_called()

        assert self.agent.last_seen is None

    def test_heartbeat_does_not_update_last_seen_on_failure(self) -> None:
        """HEAD 500 → last_seen must NOT be updated."""
        from unittest.mock import MagicMock

        from instana.agent.host import AnnounceData

        self.agent.announce_data = AnnounceData(pid=12345, agent_uuid="uuid-1")
        self.agent.last_seen = None

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(self.agent.client, "head", return_value=mock_response):
            self.agent._send_heartbeat()

        assert self.agent.last_seen is None

    def test_heartbeat_handles_connection_error_silently(self) -> None:
        """ConnectionError → no exception propagated, last_seen unchanged."""
        import requests

        from instana.agent.host import AnnounceData

        self.agent.announce_data = AnnounceData(pid=12345, agent_uuid="uuid-1")
        self.agent.last_seen = None

        with patch.object(
            self.agent.client, "head",
            side_effect=requests.exceptions.ConnectionError
        ):
            self.agent._send_heartbeat()  # must not raise

        assert self.agent.last_seen is None

    # ------------------------------------------------------------------
    # report_data_payload → heartbeat integration
    # ------------------------------------------------------------------

    def test_heartbeat_called_when_no_data_sent(self) -> None:
        """Empty payload (no spans/profiles/metrics) → _send_heartbeat is called."""
        from instana.util import DictionaryOfStan

        empty_payload = DictionaryOfStan()
        empty_payload["spans"] = []
        empty_payload["profiles"] = []
        empty_payload["metrics"]["plugins"] = []

        with patch.object(self.agent, "_send_heartbeat") as mock_hb:
            self.agent.report_data_payload(empty_payload)
            mock_hb.assert_called_once()

    def test_heartbeat_not_called_when_metrics_sent(self) -> None:
        """Metrics present and successfully sent → _send_heartbeat must NOT be called."""
        from unittest.mock import MagicMock

        from instana.agent.host import AnnounceData
        from instana.util import DictionaryOfStan

        self.agent.announce_data = AnnounceData(pid=12345, agent_uuid="uuid-1")

        payload = DictionaryOfStan()
        payload["spans"] = []
        payload["profiles"] = []
        payload["metrics"]["plugins"] = [{"data": {"ru_utime": 0.1}}]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"{}"

        with patch.object(self.agent.client, "post", return_value=mock_response), \
            patch.object(self.agent, "_send_heartbeat") as mock_hb:
            self.agent.report_data_payload(payload)
            mock_hb.assert_not_called()

    # ------------------------------------------------------------------
    # is_timed_out — poll_rate-aware threshold
    # ------------------------------------------------------------------

    def test_is_timed_out_default_threshold_60s(self) -> None:
        """Default poll_rate=1 → timeout threshold is 60 s."""
        from datetime import datetime, timedelta

        from instana.options import StandardOptions

        self.agent.options = StandardOptions()
        self.agent.options.poll_rate = 1
        self.agent.last_seen = datetime.now() - timedelta(seconds=61)

        with patch.object(self.agent.machine.fsm, "current", "good2go"):
            assert self.agent.is_timed_out()

    def test_is_timed_out_not_triggered_before_threshold(self) -> None:
        """last_seen 59 s ago with poll_rate=1 → not timed out."""
        from datetime import datetime, timedelta

        from instana.options import StandardOptions

        self.agent.options = StandardOptions()
        self.agent.options.poll_rate = 1
        self.agent.last_seen = datetime.now() - timedelta(seconds=59)

        with patch.object(self.agent.machine.fsm, "current", "good2go"):
            assert not self.agent.is_timed_out()

    def test_is_timed_out_uses_poll_rate_times_two_when_larger(self) -> None:
        """poll_rate=120 → threshold becomes 240 s, not 60 s."""
        from datetime import datetime, timedelta

        from instana.options import StandardOptions

        self.agent.options = StandardOptions()
        self.agent.options.poll_rate = 120
        # 61 s ago — would fire with old 60 s threshold, must NOT fire now
        self.agent.last_seen = datetime.now() - timedelta(seconds=61)

        with patch.object(self.agent.machine.fsm, "current", "good2go"):
            assert not self.agent.is_timed_out()

        # 241 s ago — exceeds poll_rate*2=240, must fire
        self.agent.last_seen = datetime.now() - timedelta(seconds=241)
        with patch.object(self.agent.machine.fsm, "current", "good2go"):
            assert self.agent.is_timed_out()

    def test_is_timed_out_false_when_last_seen_is_none(self) -> None:
        """last_seen=None (never connected) → not timed out."""
        self.agent.last_seen = None
        with patch.object(self.agent.machine.fsm, "current", "good2go"):
            assert not self.agent.is_timed_out()
