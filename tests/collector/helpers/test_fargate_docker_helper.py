# (c) Copyright IBM Corp. 2026

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest

from instana.collector.helpers.fargate.docker import DockerHelper

DOCKER_ID = "docker-id"


def make_container_stats() -> dict[str, Any]:
    return {
        "networks": {
            "eth0": {
                "tx_bytes": 10,
                "tx_dropped": 1,
                "tx_errors": 2,
                "tx_packets": 3,
                "rx_bytes": 20,
                "rx_dropped": 4,
                "rx_errors": 5,
                "rx_packets": 6,
            },
            "eth1": {"tx_bytes": 5, "rx_bytes": 5},
            "lo": {"tx_bytes": 1000, "rx_bytes": 1000},
        },
        "cpu_stats": {
            "cpu_usage": {
                "total_usage": 50,
                "usage_in_usermode": 30,
                "usage_in_kernelmode": 20,
            },
            "system_cpu_usage": 100,
            "online_cpus": 2,
            "throttling_data": {"periods": 8, "throttled_time": 9},
        },
        "memory_stats": {
            "usage": 100,
            "max_usage": 200,
            "limit": 300,
            "stats": {
                "active_anon": 1,
                "active_file": 2,
                "inactive_anon": 3,
                "inactive_file": 4,
                "total_cache": 5,
                "total_rss": 6,
            },
        },
        "blkio_stats": {
            "io_service_bytes_recursive": [
                {"op": "Read", "value": 100},
                {"op": "Write", "value": 200},
                {"op": "Total", "value": 300},
            ]
        },
    }


def make_plugin_data() -> dict[str, Any]:
    from instana.util import DictionaryOfStan

    return {"name": "com.instana.plugin.docker", "data": DictionaryOfStan()}


class TestDockerHelper:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.collector = MagicMock()
        self.collector.task_metadata = {
            "Containers": [
                {
                    "DockerId": DOCKER_ID,
                    "Name": "my-container",
                    "CreatedAt": "created",
                    "StartedAt": "started",
                    "Image": "image",
                    "Labels": {"com.amazonaws.ecs.task-arn": "task-arn"},
                    "Ports": [{"ContainerPort": 80}],
                    "Networks": [{"NetworkMode": "awsvpc"}],
                }
            ]
        }
        self.collector.task_stats_metadata = {DOCKER_ID: make_container_stats()}
        self.helper = DockerHelper(self.collector)
        yield
        self.helper = None

    def test_collect_metrics_without_metadata(self) -> None:
        self.collector.task_metadata = None
        assert self.helper.collect_metrics() == []

    def test_collect_metrics_without_snapshot(self) -> None:
        plugins = self.helper.collect_metrics()
        assert len(plugins) == 1
        plugin = plugins[0]
        assert plugin["name"] == "com.instana.plugin.docker"
        assert plugin["entityId"] == "task-arn::my-container"
        assert plugin["data"]["Id"] == DOCKER_ID
        assert "Created" not in plugin["data"]
        assert plugin["data"]["tx"]["bytes"] == 15
        assert plugin["data"]["tx"]["dropped"] == 1
        assert plugin["data"]["tx"]["errors"] == 2
        assert plugin["data"]["tx"]["packets"] == 3
        assert plugin["data"]["rx"]["bytes"] == 25
        assert plugin["data"]["rx"]["dropped"] == 4
        assert plugin["data"]["rx"]["errors"] == 5
        assert plugin["data"]["rx"]["packets"] == 6

    def test_collect_metrics_cpu(self) -> None:
        cpu = self.helper.collect_metrics()[0]["data"]["cpu"]
        assert cpu["total_usage"] == 1.0
        assert cpu["user_usage"] == 0.6
        assert cpu["system_usage"] == 0.4
        assert cpu["throttling_count"] == 8
        assert cpu["throttling_time"] == 9

    def test_collect_metrics_memory(self) -> None:
        memory = self.helper.collect_metrics()[0]["data"]["memory"]
        assert memory["usage"] == 100
        assert memory["max_usage"] == 200
        assert memory["limit"] == 300
        assert memory["active_anon"] == 1
        assert memory["active_file"] == 2
        assert memory["inactive_anon"] == 3
        assert memory["inactive_file"] == 4
        assert memory["total_cache"] == 5
        assert memory["total_rss"] == 6

    def test_collect_metrics_blkio(self) -> None:
        blkio = self.helper.collect_metrics()[0]["data"]["blkio"]
        assert blkio["blk_read"] == 100
        assert blkio["blk_write"] == 200
        assert self.helper.previous_blkio[DOCKER_ID]["blk_read"] == 100
        assert self.helper.previous_blkio[DOCKER_ID]["blk_write"] == 200

    def test_collect_metrics_blkio_reports_delta_on_second_run(self) -> None:
        self.helper.collect_metrics()
        stats = self.collector.task_stats_metadata[DOCKER_ID]
        stats["blkio_stats"]["io_service_bytes_recursive"] = [
            {"op": "Read", "value": 150},
            {"op": "Write", "value": 200},
        ]
        blkio = self.helper.collect_metrics()[0]["data"]["blkio"]
        assert blkio["blk_read"] == 50
        assert blkio["blk_write"] == 0
        assert self.helper.previous_blkio[DOCKER_ID]["blk_write"] == 200
        assert self.helper.previous_blkio[DOCKER_ID]["blk_read"] == 150

    def test_collect_metrics_unchanged_values_are_not_resent(self) -> None:
        self.helper.collect_metrics()
        plugin = self.helper.collect_metrics()[0]
        assert not plugin["data"]["tx"]
        assert not plugin["data"]["rx"]
        assert not plugin["data"]["memory"]
        assert not plugin["data"]["cpu"]

    def test_collect_metrics_with_snapshot_resends_values(self) -> None:
        self.helper.collect_metrics()
        plugin = self.helper.collect_metrics(with_snapshot=True)[0]
        assert plugin["data"]["tx"]["bytes"] == 15
        assert plugin["data"]["memory"]["usage"] == 100
        assert plugin["data"]["Created"] == "created"
        assert plugin["data"]["Started"] == "started"
        assert plugin["data"]["Image"] == "image"
        assert plugin["data"]["Labels"] == {"com.amazonaws.ecs.task-arn": "task-arn"}
        assert plugin["data"]["Ports"] == [{"ContainerPort": 80}]
        assert plugin["data"]["NetworkMode"] == "awsvpc"

    def test_collect_metrics_snapshot_without_networks(self) -> None:
        self.collector.task_metadata["Containers"][0]["Networks"] = []
        plugin = self.helper.collect_metrics(with_snapshot=True)[0]
        assert "NetworkMode" not in plugin["data"]

    def test_collect_metrics_unknown_container_stats(self) -> None:
        self.collector.task_stats_metadata = {}
        plugin = self.helper.collect_metrics()[0]
        assert plugin["data"]["Id"] == DOCKER_ID
        assert "tx" not in plugin["data"]

    def test_collect_metrics_missing_optional_sections(self) -> None:
        self.collector.task_stats_metadata = {
            DOCKER_ID: {"cpu_stats": {}, "blkio_stats": {}}
        }
        plugin = self.helper.collect_metrics()[0]
        assert "tx" not in plugin["data"]
        assert "cpu" not in plugin["data"]
        assert "blkio" not in plugin["data"]

    def test_collect_metrics_outer_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.collector.task_metadata = {"Containers": [5]}
        assert self.helper.collect_metrics() == []
        assert "DockerHelper.collect_metrics" in caplog.text

    def test_collect_container_snapshot_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        plugin_data = make_plugin_data()
        self.helper._collect_container_snapshot(plugin_data, {"Networks": None})
        assert "_collect_container_snapshot" in caplog.text

    @pytest.mark.parametrize(
        "method, message",
        [
            ("_collect_network_metrics", "_collect_network_metrics"),
            ("_collect_cpu_metrics", "_collect_cpu_metrics"),
            ("_collect_memory_metrics", "_collect_memory_metrics"),
            ("_collect_blkio_metrics", "_collect_blkio_metrics"),
        ],
    )
    def test_collect_metrics_helpers_log_exceptions(
        self, method: str, message: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        plugin_data = make_plugin_data()
        container = {
            "networks": {"eth0": "not-a-dict"},
            "cpu_stats": {"cpu_usage": {}, "system_cpu_usage": 1},
            "memory_stats": "not-a-dict",
            "blkio_stats": {"io_service_bytes_recursive": [{}]},
        }
        getattr(self.helper, method)(container, plugin_data, DOCKER_ID, False)
        assert message in caplog.text
