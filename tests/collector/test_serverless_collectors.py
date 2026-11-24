# (c) Copyright IBM Corp. 2026

import json
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from instana.collector.aws_eks_fargate import EKSFargateCollector
from instana.collector.aws_fargate import AWSFargateCollector
from instana.collector.google_cloud_run import GCRCollector
from instana.collector.helpers.google_cloud_run.instance_entity import (
    InstanceEntityHelper,
)

ECMU = "http://169.254.170.2/v3/abc"


class FakeHelper:
    def __init__(self, plugins=None, error=None) -> None:
        self.plugins = plugins if plugins is not None else []
        self.error = error
        self.kwargs = None

    def collect_metrics(self, **kwargs: object) -> list[dict[str, str]]:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.plugins


def make_response(payload) -> MagicMock:
    response = MagicMock()
    response.content = json.dumps(payload)
    response.json.return_value = payload
    return response


class TestAWSFargateCollector:
    @pytest.fixture(autouse=True)
    def _resource(self, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
        monkeypatch.setenv("ECS_CONTAINER_METADATA_URI", ECMU)
        self.collector = AWSFargateCollector(MagicMock())
        yield
        self.collector = None

    def test_init_valid_metadata_uri_sets_urls_and_helpers(self) -> None:
        assert self.collector.ready_to_start is True
        assert self.collector.ecmu_url_root == ECMU
        assert self.collector.ecmu_url_task == f"{ECMU}/task"
        assert self.collector.ecmu_url_stats == f"{ECMU}/stats"
        assert self.collector.ecmu_url_task_stats == f"{ECMU}/task/stats"
        assert len(self.collector.helpers) == 5

    @pytest.mark.parametrize("value", ["", "not a url"])
    def test_init_invalid_metadata_uri(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ECS_CONTAINER_METADATA_URI", value)
        collector = AWSFargateCollector(MagicMock())
        assert collector.ready_to_start is False

    def test_start_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ECS_CONTAINER_METADATA_URI", "")
        collector = AWSFargateCollector(MagicMock())
        collector.start()
        assert collector.started is False
        assert collector.reporting_thread is None

    def test_start_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        start = MagicMock()
        monkeypatch.setattr("instana.collector.base.BaseCollector.start", start)
        self.collector.start()
        start.assert_called_once()

    def test_get_ecs_metadata_full_fetch(self) -> None:
        responses = {
            self.collector.ecmu_url_root: {"Name": "root"},
            self.collector.ecmu_url_task: {"TaskARN": "task"},
            self.collector.ecmu_url_stats: {"stats": 1},
            self.collector.ecmu_url_task_stats: {"task_stats": 2},
        }
        self.collector.http_client = MagicMock()
        self.collector.http_client.get.side_effect = lambda url, timeout: make_response(
            responses[url]
        )
        self.collector.get_ecs_metadata()
        assert self.collector.root_metadata == {"Name": "root"}
        assert self.collector.task_metadata == {"TaskARN": "task"}
        assert self.collector.stats_metadata == {"stats": 1}
        assert self.collector.task_stats_metadata == {"task_stats": 2}
        assert self.collector.http_client.get.call_count == 4
        assert self.collector.last_ecmu_full_fetch > 0

    def test_get_ecs_metadata_partial_fetch(self) -> None:
        self.collector.last_ecmu_full_fetch = 2**40
        self.collector.http_client = MagicMock()
        self.collector.http_client.get.return_value = make_response({"k": "v"})
        self.collector.get_ecs_metadata()
        assert self.collector.root_metadata is None
        assert self.collector.task_metadata is None
        assert self.collector.stats_metadata == {"k": "v"}
        assert self.collector.task_stats_metadata == {"k": "v"}
        assert self.collector.http_client.get.call_count == 2

    def test_get_ecs_metadata_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.collector.http_client = MagicMock()
        self.collector.http_client.get.side_effect = RuntimeError("boom")
        self.collector.get_ecs_metadata()
        assert self.collector.root_metadata is None
        assert "AWSFargateCollector.get_ecs_metadata" in caplog.text

    def test_should_send_snapshot_data_by_interval(self) -> None:
        self.collector.snapshot_data_last_sent = 0
        assert self.collector.should_send_snapshot_data() is True
        self.collector.snapshot_data_last_sent = 2**40
        assert self.collector.should_send_snapshot_data() is False

    def test_prepare_payload_with_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(self.collector, "get_ecs_metadata", MagicMock())
        helper = FakeHelper(plugins=[{"name": "plugin"}])
        self.collector.helpers = [helper, helper]
        payload = self.collector.prepare_payload()
        assert payload["spans"] == []
        assert payload["metrics"]["plugins"] == [{"name": "plugin"}] * 2
        assert helper.kwargs == {"with_snapshot": True}
        assert self.collector.snapshot_data_last_sent > 0
        self.collector.get_ecs_metadata.assert_called_once()

    def test_prepare_payload_without_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(self.collector, "get_ecs_metadata", MagicMock())
        self.collector.snapshot_data_last_sent = 2**40
        helper = FakeHelper()
        self.collector.helpers = [helper]
        payload = self.collector.prepare_payload()
        assert helper.kwargs == {"with_snapshot": False}
        assert payload["metrics"]["plugins"] == []
        assert self.collector.snapshot_data_last_sent == 2**40

    def test_prepare_payload_with_spans(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(self.collector, "get_ecs_metadata", MagicMock())
        monkeypatch.setattr(
            "instana.collector.aws_fargate.format_span", lambda spans: ["formatted"]
        )
        monkeypatch.setattr(self.collector, "queued_spans", lambda: ["span"])
        self.collector.span_queue.put("span")
        self.collector.helpers = []
        payload = self.collector.prepare_payload()
        assert payload["spans"] == ["formatted"]

    def test_prepare_payload_exception(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        monkeypatch.setattr(self.collector, "get_ecs_metadata", MagicMock())
        self.collector.helpers = [FakeHelper(error=RuntimeError("boom"))]
        payload = self.collector.prepare_payload()
        assert payload["metrics"]["plugins"] == []
        assert "collect_snapshot error" in caplog.text

    def test_get_fq_arn_without_metadata(self) -> None:
        assert self.collector.get_fq_arn() == "Missing ECMU metadata"

    def test_get_fq_arn_with_metadata(self) -> None:
        self.collector.root_metadata = {
            "Name": "container",
            "Labels": {"com.amazonaws.ecs.task-arn": "arn:task"},
        }
        assert self.collector.get_fq_arn() == "arn:task::container"
        self.collector.root_metadata = None
        assert self.collector.get_fq_arn() == "arn:task::container"

    def test_get_fq_arn_without_labels(self) -> None:
        self.collector.root_metadata = {"Name": "container"}
        assert self.collector.get_fq_arn() == "::container"


class TestEKSFargateCollector:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        agent = MagicMock()
        agent.podname = "my-pod"
        self.collector = EKSFargateCollector(agent)
        yield
        self.collector = None

    def test_init_sets_podname_and_helpers(self) -> None:
        assert self.collector.podname == "my-pod"
        assert self.collector.snapshot_data_sent is False
        assert len(self.collector.helpers) == 2

    def test_should_send_snapshot_data_by_interval(self) -> None:
        self.collector.snapshot_data_last_sent = 0
        assert self.collector.should_send_snapshot_data() is True
        self.collector.snapshot_data_last_sent = 2**40
        assert self.collector.should_send_snapshot_data() is False

    def test_prepare_payload_with_snapshot(self) -> None:
        helper = FakeHelper(plugins=[{"name": "plugin"}])
        self.collector.helpers = [helper]
        payload = self.collector.prepare_payload()
        assert payload["metrics"]["plugins"] == [{"name": "plugin"}]
        assert helper.kwargs == {"with_snapshot": True}
        assert self.collector.snapshot_data_last_sent > 0

    def test_prepare_payload_without_snapshot(self) -> None:
        self.collector.snapshot_data_last_sent = 2**40
        helper = FakeHelper()
        self.collector.helpers = [helper]
        self.collector.prepare_payload()
        assert helper.kwargs == {"with_snapshot": False}
        assert self.collector.snapshot_data_last_sent == 2**40

    def test_prepare_payload_with_spans(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "instana.collector.aws_eks_fargate.format_span",
            lambda spans: ["formatted"],
        )
        monkeypatch.setattr(self.collector, "queued_spans", lambda: ["span"])
        self.collector.span_queue.put("span")
        self.collector.helpers = []
        assert self.collector.prepare_payload()["spans"] == ["formatted"]

    def test_prepare_payload_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.collector.helpers = [FakeHelper(error=RuntimeError("boom"))]
        payload = self.collector.prepare_payload()
        assert payload["metrics"]["plugins"] == []
        assert "prepare_payload error" in caplog.text


class TestGCRCollector:
    @pytest.fixture(autouse=True)
    def _resource(self, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
        monkeypatch.delenv("GOOGLE_CLOUD_RUN_METADATA_ENDPOINT", raising=False)
        self.collector = GCRCollector(MagicMock(), "service", "config", "rev")
        yield
        self.collector = None

    def test_init_default_endpoint_sets_urls_and_helpers(self) -> None:
        assert self.collector.ready_to_start is True
        assert self.collector.service == "service"
        assert self.collector.configuration == "config"
        assert self.collector.revision == "rev"
        assert self.collector._gcr_md_project_uri == (
            "http://metadata.google.internal/computeMetadata/v1/project/?recursive=true"
        )
        assert self.collector._gcr_md_instance_uri == (
            "http://metadata.google.internal/computeMetadata/v1/instance/?recursive=true"
        )
        assert len(self.collector.helpers) == 2

    @pytest.mark.parametrize("value", ["", "not a url"])
    def test_init_invalid_metadata_endpoint(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_RUN_METADATA_ENDPOINT", value)
        collector = GCRCollector(MagicMock(), "service", "config", "rev")
        assert collector.ready_to_start is False

    def test_start_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_RUN_METADATA_ENDPOINT", "")
        collector = GCRCollector(MagicMock(), "service", "config", "rev")
        collector.start()
        assert collector.started is False

    def test_start_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        start = MagicMock()
        monkeypatch.setattr("instana.collector.base.BaseCollector.start", start)
        self.collector.start()
        start.assert_called_once()

    def test_get_project_instance_metadata_stores_responses(self) -> None:
        responses = {
            self.collector._gcr_md_project_uri: {"projectId": "project"},
            self.collector._gcr_md_instance_uri: {"id": "instance"},
        }
        self.collector._http_client = MagicMock()
        self.collector._http_client.get.side_effect = lambda url, **kwargs: (
            make_response(responses[url])
        )
        self.collector._GCRCollector__get_project_instance_metadata()
        assert self.collector.project_metadata == {"projectId": "project"}
        assert self.collector.instance_metadata == {"id": "instance"}
        assert self.collector._GCRCollector__last_gcr_md_full_fetch > 0
        for call in self.collector._http_client.get.call_args_list:
            assert call.kwargs["headers"] == {"Metadata-Flavor": "Google"}

    def test_get_project_instance_metadata_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.collector._http_client = MagicMock()
        self.collector._http_client.get.side_effect = RuntimeError("boom")
        self.collector._GCRCollector__get_project_instance_metadata()
        assert self.collector.project_metadata is None
        assert "get_project_instance_metadata" in caplog.text

    def test_should_send_snapshot_data_by_interval(self) -> None:
        self.collector.snapshot_data_last_sent = 0
        assert self.collector.should_send_snapshot_data() is True
        self.collector.snapshot_data_last_sent = 2**40
        assert self.collector.should_send_snapshot_data() is False

    def prepare(self, monkeypatch: pytest.MonkeyPatch, instance, project) -> FakeHelper:
        def fake_fetch() -> None:
            self.collector.instance_metadata = instance
            self.collector.project_metadata = project

        monkeypatch.setattr(
            self.collector, "_GCRCollector__get_project_instance_metadata", fake_fetch
        )
        helper = FakeHelper(plugins=[{"name": "plugin"}])
        self.collector.helpers = [helper]
        return helper

    def test_prepare_payload_with_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        helper = self.prepare(monkeypatch, {"id": "i"}, {"projectId": "p"})
        payload = self.collector.prepare_payload()
        assert payload["metrics"]["plugins"] == [{"name": "plugin"}]
        assert helper.kwargs == {
            "with_snapshot": True,
            "instance_metadata": {"id": "i"},
            "project_metadata": {"projectId": "p"},
        }
        assert self.collector.snapshot_data_last_sent > 0

    def test_prepare_payload_without_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        helper = self.prepare(monkeypatch, {"id": "i"}, None)
        self.collector.snapshot_data_last_sent = 2**40
        self.collector.prepare_payload()
        assert helper.kwargs["with_snapshot"] is False
        assert self.collector.snapshot_data_last_sent == 2**40

    def test_prepare_payload_without_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        helper = self.prepare(monkeypatch, None, None)
        payload = self.collector.prepare_payload()
        assert payload["metrics"]["plugins"] == []
        assert helper.kwargs is None

    def test_prepare_payload_skipped_within_fetch_interval(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        helper = self.prepare(monkeypatch, {"id": "i"}, {})
        self.collector._GCRCollector__last_gcr_md_full_fetch = 2**40
        # fetching_start_time is set to "now", so delta is negative (< interval)
        payload = self.collector.prepare_payload()
        assert payload["metrics"]["plugins"] == []
        assert helper.kwargs is None

    def test_prepare_payload_with_spans(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.prepare(monkeypatch, {"id": "i"}, {})
        monkeypatch.setattr(
            "instana.collector.google_cloud_run.format_span",
            lambda spans: ["formatted"],
        )
        monkeypatch.setattr(self.collector, "queued_spans", lambda: ["span"])
        self.collector.span_queue.put("span")
        assert self.collector.prepare_payload()["spans"] == ["formatted"]

    def test_prepare_payload_exception(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.prepare(monkeypatch, {"id": "i"}, {})
        self.collector.helpers = [FakeHelper(error=RuntimeError("boom"))]
        payload = self.collector.prepare_payload()
        assert payload["metrics"]["plugins"] == []
        assert "collect_snapshot error" in caplog.text

    def test_get_instance_id_with_and_without_metadata(self) -> None:
        assert self.collector.get_instance_id() is None
        self.collector.instance_metadata = {"id": "instance-id"}
        assert self.collector.get_instance_id() == "instance-id"

    def test_get_instance_id_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("DEBUG", logger="instana")
        self.collector.instance_metadata = ["not-a-dict"]
        assert self.collector.get_instance_id() is None
        assert "get_instance_id error" in caplog.text


class TestInstanceEntityHelper:
    @pytest.fixture(autouse=True)
    def _resource(self, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
        monkeypatch.setenv("PORT", "8080")
        self.collector = MagicMock()
        self.collector.service = "service"
        self.collector.configuration = "config"
        self.collector.revision = "rev"
        self.helper = InstanceEntityHelper(self.collector)
        yield
        self.helper = None

    def test_collect_metrics_builds_instance_entity(self) -> None:
        plugins = self.helper.collect_metrics(
            instance_metadata={"id": "instance", "region": "projects/1/regions/eu"},
            project_metadata={"numericProjectId": 1, "projectId": "project"},
        )
        assert len(plugins) == 1
        plugin = plugins[0]
        assert plugin["name"] == "com.instana.plugin.gcp.run.revision.instance"
        assert plugin["entityId"] == "instance"
        data = plugin["data"]
        assert data["runtime"] == "python"
        assert data["region"] == "eu"
        assert data["service"] == "service"
        assert data["configuration"] == "config"
        assert data["revision"] == "rev"
        assert data["instanceId"] == "instance"
        assert data["port"] == "8080"
        assert data["numericProjectId"] == 1
        assert data["projectId"] == "project"

    def test_collect_metrics_exception_still_appends_plugin(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level("DEBUG", logger="instana")
        plugins = self.helper.collect_metrics()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "com.instana.plugin.gcp.run.revision.instance"
        assert "collect_service_revision_entity_metrics" in caplog.text
