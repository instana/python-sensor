# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import gc
import logging
import os
import sys
import threading
from typing import Generator

import pytest
from instana.collector.helpers.runtime import (
    PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR,
)
from instana.collector.host import HostCollector
from instana.singletons import get_agent, get_tracer
from instana.version import VERSION
from mock import patch
from pytest import LogCaptureFixture


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

    def test_prepare_payload_basics(self) -> None:
        with patch.object(gc, "isenabled", return_value=True):
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
            assert "Manual" == python_plugin["data"]["snapshot"]["m"]
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

            assert "gc" in python_plugin["data"]["metrics"]
            assert isinstance(python_plugin["data"]["metrics"]["gc"], dict)
            assert "collect0" in python_plugin["data"]["metrics"]["gc"]
            assert type(python_plugin["data"]["metrics"]["gc"]["collect0"]) in [
                float,
                int,
            ]
            assert "collect1" in python_plugin["data"]["metrics"]["gc"]
            assert type(python_plugin["data"]["metrics"]["gc"]["collect1"]) in [
                float,
                int,
            ]
            assert "collect2" in python_plugin["data"]["metrics"]["gc"]
            assert type(python_plugin["data"]["metrics"]["gc"]["collect2"]) in [
                float,
                int,
            ]
            assert "threshold0" in python_plugin["data"]["metrics"]["gc"]
            assert type(python_plugin["data"]["metrics"]["gc"]["threshold0"]) in [
                float,
                int,
            ]
            assert "threshold1" in python_plugin["data"]["metrics"]["gc"]
            assert type(python_plugin["data"]["metrics"]["gc"]["threshold1"]) in [
                float,
                int,
            ]
            assert "threshold2" in python_plugin["data"]["metrics"]["gc"]
            assert type(python_plugin["data"]["metrics"]["gc"]["threshold2"]) in [
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
        assert "Manual" == python_plugin["data"]["snapshot"]["m"]
        assert "metrics" not in python_plugin["data"]

    def test_prepare_payload_with_snapshot_with_python_packages(self) -> None:
        self.payload = self.agent.collector.prepare_payload()
        assert self.payload
        assert "snapshot" in self.payload["metrics"]["plugins"][0]["data"]
        snapshot = self.payload["metrics"]["plugins"][0]["data"]["snapshot"]
        assert snapshot
        assert "m" in snapshot
        assert "Manual" == snapshot["m"]
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
        assert "Manual" == snapshot["m"]
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
        assert "Autowrapt" == snapshot["m"]
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
        assert "AutoTrace" == snapshot["m"]
        assert "version" in snapshot
        assert len(snapshot["versions"]) > 5
        expected_packages = ("instana", "wrapt", "fysom")
        for package in expected_packages:
            assert (
                package in snapshot["versions"]
            ), f"{package} not found in snapshot['versions']"
        assert snapshot["versions"]["instana"] == VERSION
