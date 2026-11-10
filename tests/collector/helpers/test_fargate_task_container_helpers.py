# (c) Copyright IBM Corp. 2026

from collections.abc import Generator
from unittest.mock import MagicMock, PropertyMock

import pytest

from instana.collector.helpers.fargate.container import ContainerHelper
from instana.collector.helpers.fargate.task import TaskHelper

TASK_ARN = "arn:aws:ecs:us-east-2:123:task/abc"

CONTAINER = {
    "DockerId": "docker-id",
    "Name": "my-container",
    "DockerName": "ecs-my-container",
    "Image": "my/image:latest",
    "ImageID": "sha256:abc",
    "DesiredStatus": "RUNNING",
    "KnownStatus": "RUNNING",
    "Ports": [{"ContainerPort": 80}],
    "CreatedAt": "2025-01-01T00:00:00Z",
    "StartedAt": "2025-01-01T00:00:01Z",
    "Type": "NORMAL",
    "Limits": {"CPU": 2, "Memory": 512},
    "Labels": {
        "com.amazonaws.ecs.task-arn": TASK_ARN,
        "com.amazonaws.ecs.task-definition-family": "family",
        "com.amazonaws.ecs.task-definition-version": "7",
        "com.amazonaws.ecs.cluster": "cluster-arn",
    },
}

TASK_METADATA = {
    "TaskARN": TASK_ARN,
    "Cluster": "cluster-arn",
    "Family": "family",
    "Revision": "7",
    "AvailabilityZone": "us-east-2a",
    "DesiredStatus": "RUNNING",
    "KnownStatus": "RUNNING",
    "PullStartedAt": "start",
    "PullStoppeddAt": "stop",
    "Limits": {"CPU": 1, "Memory": 1024},
    "Containers": [CONTAINER],
}


class TestTaskHelper:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.collector = MagicMock()
        self.collector.task_metadata = dict(TASK_METADATA)
        self.collector.agent.options.zone = None
        self.collector.agent.options.tags = None
        self.helper = TaskHelper(self.collector)
        yield
        self.helper = None

    def test_collect_metrics_without_metadata(self) -> None:
        self.collector.task_metadata = None
        assert self.helper.collect_metrics() == []

    def test_collect_metrics_without_snapshot(self) -> None:
        plugins = self.helper.collect_metrics()
        assert len(plugins) == 1
        plugin = plugins[0]
        assert plugin["name"] == "com.instana.plugin.aws.ecs.task"
        assert plugin["entityId"] == TASK_ARN
        assert plugin["data"]["taskArn"] == TASK_ARN
        assert plugin["data"]["clusterArn"] == "cluster-arn"
        assert plugin["data"]["taskDefinition"] == "family"
        assert plugin["data"]["taskDefinitionVersion"] == "7"
        assert plugin["data"]["availabilityZone"] == "us-east-2a"
        assert "desiredStatus" not in plugin["data"]

    def test_collect_metrics_with_snapshot(self) -> None:
        plugin = self.helper.collect_metrics(with_snapshot=True)[0]
        assert plugin["data"]["desiredStatus"] == "RUNNING"
        assert plugin["data"]["knownStatus"] == "RUNNING"
        assert plugin["data"]["pullStartedAt"] == "start"
        assert plugin["data"]["pullStoppedAt"] == "stop"
        assert plugin["data"]["limits"]["cpu"] == 1
        assert plugin["data"]["limits"]["memory"] == 1024
        assert "instanaZone" not in plugin["data"]
        assert "tags" not in plugin["data"]

    def test_collect_metrics_with_snapshot_zone_and_tags(self) -> None:
        self.collector.agent.options.zone = "zone-a"
        self.collector.agent.options.tags = {"env": "test"}
        plugin = self.helper.collect_metrics(with_snapshot=True)[0]
        assert plugin["data"]["instanaZone"] == "zone-a"
        assert plugin["data"]["tags"] == {"env": "test"}

    def test_collect_metrics_inner_exception_still_appends_plugin(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.collector.task_metadata = {"Limits": None}
        plugins = self.helper.collect_metrics(with_snapshot=True)
        assert len(plugins) == 1
        assert plugins[0]["name"] == "com.instana.plugin.aws.ecs.task"
        assert "collect_task_metrics" in caplog.text

    def test_collect_metrics_outer_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        type(self.collector).task_metadata = PropertyMock(
            side_effect=RuntimeError("boom")
        )
        assert self.helper.collect_metrics() == []
        assert "collect_task_metrics" in caplog.text


class TestContainerHelper:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.collector = MagicMock()
        self.collector.task_metadata = dict(TASK_METADATA)
        self.collector.root_metadata = {"Name": "my-container"}
        self.helper = ContainerHelper(self.collector)
        yield
        self.helper = None

    def test_collect_metrics_without_metadata(self) -> None:
        self.collector.task_metadata = None
        assert self.helper.collect_metrics() == []

    def test_collect_metrics_without_containers(self) -> None:
        self.collector.task_metadata = {}
        assert self.helper.collect_metrics() == []

    def test_collect_metrics_without_snapshot(self) -> None:
        plugins = self.helper.collect_metrics()
        assert len(plugins) == 1
        plugin = plugins[0]
        assert plugin["name"] == "com.instana.plugin.aws.ecs.container"
        assert plugin["entityId"] == f"{TASK_ARN}::my-container"
        assert plugin["data"]["instrumented"] is True
        assert plugin["data"]["dockerId"] == "docker-id"
        assert plugin["data"]["taskArn"] == TASK_ARN
        assert "runtime" not in plugin["data"]

    def test_collect_metrics_not_instrumented_container(self) -> None:
        self.collector.root_metadata = {"Name": "other-container"}
        plugin = self.helper.collect_metrics()[0]
        assert "instrumented" not in plugin["data"]

    def test_collect_metrics_with_snapshot(self) -> None:
        data = self.helper.collect_metrics(with_snapshot=True)[0]["data"]
        assert data["runtime"] == "python"
        assert data["dockerName"] == "ecs-my-container"
        assert data["containerName"] == "my-container"
        assert data["image"] == "my/image:latest"
        assert data["imageId"] == "sha256:abc"
        assert data["taskDefinition"] == "family"
        assert data["taskDefinitionVersion"] == "7"
        assert data["clusterArn"] == "cluster-arn"
        assert data["desiredStatus"] == "RUNNING"
        assert data["knownStatus"] == "RUNNING"
        assert data["ports"] == [{"ContainerPort": 80}]
        assert data["createdAt"] == "2025-01-01T00:00:00Z"
        assert data["startedAt"] == "2025-01-01T00:00:01Z"
        assert data["type"] == "NORMAL"
        assert data["limits"]["cpu"] == 2
        assert data["limits"]["memory"] == 512

    def test_collect_metrics_inner_exception_still_appends_plugin(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.collector.root_metadata = {}
        plugins = self.helper.collect_metrics()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "com.instana.plugin.aws.ecs.container"
        assert "_collect_container_snapshots" in caplog.text

    def test_collect_metrics_outer_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.collector.task_metadata = {"Containers": 5}
        assert self.helper.collect_metrics() == []
        assert "collect_container_metrics" in caplog.text
