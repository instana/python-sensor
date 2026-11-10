# (c) Copyright IBM Corp. 2026

import os
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from instana.collector.helpers.process import ProcessHelper


class TestProcessHelper:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.collector = MagicMock()
        self.collector.agent.options.secrets_matcher = "contains"
        self.collector.agent.options.secrets_list = ["KEY", "PASSWORD", "SECRET"]
        self.collector.fetching_start_time = 1234
        self.helper = ProcessHelper(self.collector)
        os.environ["INSTANA_TEST_PLAIN_VAR"] = "visible"
        os.environ["INSTANA_TEST_PASSWORD"] = "hidden"
        yield
        os.environ.pop("INSTANA_TEST_PLAIN_VAR", None)
        os.environ.pop("INSTANA_TEST_PASSWORD", None)
        self.helper = None

    def test_collect_metrics_without_snapshot(self) -> None:
        plugin_data = self.helper.collect_metrics()
        assert plugin_data["name"] == "com.instana.plugin.process"
        assert plugin_data["entityId"] == str(os.getpid())
        assert plugin_data["data"]["pid"] == os.getpid()
        assert "env" not in plugin_data["data"]

    def test_collect_metrics_with_snapshot(self) -> None:
        plugin_data = self.helper.collect_metrics(with_snapshot=True)
        data = plugin_data["data"]
        assert data["pid"] == os.getpid()
        assert data["env"]["INSTANA_TEST_PLAIN_VAR"] == "visible"
        assert data["env"]["INSTANA_TEST_PASSWORD"] == "<ignored>"
        assert data["start"] == 1234
        assert isinstance(data["args"], list)

    def test_collect_metrics_exception(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        monkeypatch.setattr(
            "instana.collector.helpers.process.DictionaryOfStan",
            MagicMock(side_effect=RuntimeError("boom")),
        )
        plugin_data = self.helper.collect_metrics()
        assert "data" not in plugin_data
        assert "ProcessHelper.collect_metrics" in caplog.text

    def test_collect_process_snapshot_exec_path_missing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        monkeypatch.setattr(
            "instana.collector.helpers.process.os.path.isfile",
            lambda path: False,
        )
        plugin_data = self.helper.collect_metrics(with_snapshot=True)
        assert "exec" not in plugin_data["data"]
        assert "Can't access /proc/self/exe" in caplog.text

    def test_collect_process_snapshot_exec_path_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "instana.collector.helpers.process.os.path.isfile",
            lambda path: True,
        )
        monkeypatch.setattr(
            "instana.collector.helpers.process.os.readlink",
            lambda path: "/usr/bin/python",
        )
        plugin_data = self.helper.collect_metrics(with_snapshot=True)
        assert plugin_data["data"]["exec"] == "/usr/bin/python"

    def test_collect_process_snapshot_drops_exe_from_cmdline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "instana.collector.helpers.process.get_proc_cmdline",
            lambda: ["python", "app.py", "--flag"],
        )
        plugin_data = self.helper.collect_metrics(with_snapshot=True)
        assert plugin_data["data"]["args"] == ["app.py", "--flag"]

    def test_collect_process_snapshot_user_lookup_error(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        monkeypatch.setattr(
            "instana.collector.helpers.process.pwd.getpwuid",
            MagicMock(side_effect=KeyError("no user")),
        )
        plugin_data = self.helper.collect_metrics(with_snapshot=True)
        assert "user" not in plugin_data["data"]
        assert plugin_data["data"]["start"] == 1234
        assert "euid/egid detection" in caplog.text

    def test_collect_process_snapshot_exception(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        monkeypatch.setattr(
            "instana.collector.helpers.process.contains_secret",
            MagicMock(side_effect=RuntimeError("boom")),
        )
        plugin_data = self.helper.collect_metrics(with_snapshot=True)
        assert "env" not in plugin_data["data"]
        assert "ProcessHelper._collect_process_snapshot" in caplog.text
