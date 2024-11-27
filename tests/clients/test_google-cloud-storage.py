# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import sys
from typing import Generator
import json
import pytest
import requests
import io

from instana.singletons import agent, tracer
from instana.span.span import get_current_span
from tests.test_utils import _TraceContextMixin
from opentelemetry.trace import SpanKind

from mock import patch, Mock
from six.moves import http_client

from google.cloud import storage
from google.api_core import iam, page_iterator
from google.auth.credentials import AnonymousCredentials


class TestGoogleCloudStorage(_TraceContextMixin):
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        yield
        agent.options.allow_exit_as_root = False

    @patch("requests.Session.request")
    def test_buckets_list(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#buckets", "items": []},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            buckets = client.list_buckets()
            for _ in buckets:
                pass

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.list"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"

    @patch("requests.Session.request")
    def test_buckets_list_as_root_exit_span(self, mock_requests: Mock) -> None:
        agent.options.allow_exit_as_root = True
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#buckets", "items": []},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        buckets = client.list_buckets()
        for _ in buckets:
            pass

        spans = self.recorder.queued_spans()

        assert len(spans) == 1

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.list"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"

    @patch("requests.Session.request")
    def test_buckets_insert(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.create_bucket("test bucket")

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.insert"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_buckets_get(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.get_bucket("test bucket")

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        assert gcs_span.t == test_span.t
        assert gcs_span.p == test_span.s

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.get"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_buckets_patch(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").patch()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.patch"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_buckets_update(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").update()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.update"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_buckets_get_iam_policy(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#policy"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").get_iam_policy()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.getIamPolicy"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_buckets_set_iam_policy(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#policy"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").set_iam_policy(iam.Policy())

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.setIamPolicy"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_buckets_test_iam_permissions(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#testIamPermissionsResponse"},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").test_iam_permissions("test-permission")

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.testIamPermissions"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_buckets_lock_retention_policy(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={
                "kind": "storage#bucket",
                "metageneration": 1,
                "retentionPolicy": {"isLocked": False},
            },
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        bucket = client.bucket("test bucket")
        bucket.reload()

        with tracer.start_as_current_span("test"):
            bucket.lock_retention_policy()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.lockRetentionPolicy"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_buckets_delete(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response()

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").delete()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "buckets.delete"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_objects_compose(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").blob("dest object").compose(
                [
                    storage.blob.Blob("object 1", "test bucket"),
                    storage.blob.Blob("object 2", "test bucket"),
                ]
            )

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.compose"
        assert gcs_span.data["gcs"]["destinationBucket"] == "test bucket"
        assert gcs_span.data["gcs"]["destinationObject"] == "dest object"
        assert (
            gcs_span.data["gcs"]["sourceObjects"]
            == "test bucket/object 1,test bucket/object 2"
        )

    @patch("requests.Session.request")
    def test_objects_copy(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )
        bucket = client.bucket("src bucket")

        with tracer.start_as_current_span("test"):
            bucket.copy_blob(
                bucket.blob("src object"),
                client.bucket("dest bucket"),
                new_name="dest object",
            )

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.copy"
        assert gcs_span.data["gcs"]["destinationBucket"] == "dest bucket"
        assert gcs_span.data["gcs"]["destinationObject"] == "dest object"
        assert gcs_span.data["gcs"]["sourceBucket"] == "src bucket"
        assert gcs_span.data["gcs"]["sourceObject"] == "src object"

    @patch("requests.Session.request")
    def test_objects_delete(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response()

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").blob("test object").delete()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.delete"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"
        assert gcs_span.data["gcs"]["object"] == "test object"

    @patch("requests.Session.request")
    def test_objects_attrs(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").blob("test object").exists()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.attrs"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"
        assert gcs_span.data["gcs"]["object"] == "test object"

    @pytest.mark.skipif(
        sys.version_info >= (3, 14),
        reason='Avoiding "Fatal Python error: Segmentation fault"',
    )
    @patch("requests.Session.request")
    def test_objects_get(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            content=b"CONTENT", status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").blob("test object").download_to_file(
                io.BytesIO(), raw_download=True
            )

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.get"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"
        assert gcs_span.data["gcs"]["object"] == "test object"

    @patch("requests.Session.request")
    def test_objects_insert(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").blob("test object").upload_from_string(
                "CONTENT"
            )

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.insert"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"
        assert gcs_span.data["gcs"]["object"] == "test object"

    @patch("requests.Session.request")
    def test_objects_list(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            blobs = client.bucket("test bucket").list_blobs()

            for _ in blobs:
                pass

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.list"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_objects_patch(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").blob("test object").patch()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.patch"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"
        assert gcs_span.data["gcs"]["object"] == "test object"

    @patch("requests.Session.request")
    def test_objects_rewrite(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={
                "kind": "storage#rewriteResponse",
                "totalBytesRewritten": 0,
                "objectSize": 0,
                "done": True,
                "resource": {},
            },
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("dest bucket").blob("dest object").rewrite(
                client.bucket("src bucket").blob("src object")
            )

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.rewrite"
        assert gcs_span.data["gcs"]["destinationBucket"] == "dest bucket"
        assert gcs_span.data["gcs"]["destinationObject"] == "dest object"
        assert gcs_span.data["gcs"]["sourceBucket"] == "src bucket"
        assert gcs_span.data["gcs"]["sourceObject"] == "src object"

    @patch("requests.Session.request")
    def test_objects_update(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").blob("test object").update()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objects.update"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"
        assert gcs_span.data["gcs"]["object"] == "test object"

    @patch("requests.Session.request")
    def test_default_acls_list(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#objectAccessControls", "items": []},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").default_object_acl.get_entities()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "defaultAcls.list"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"

    @patch("requests.Session.request")
    def test_object_acls_list(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#objectAccessControls", "items": []},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.bucket("test bucket").blob("test object").acl.get_entities()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "objectAcls.list"
        assert gcs_span.data["gcs"]["bucket"] == "test bucket"
        assert gcs_span.data["gcs"]["object"] == "test object"

    @patch("requests.Session.request")
    def test_object_hmac_keys_create(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#hmacKey", "metadata": {}, "secret": ""},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.create_hmac_key("test@example.com")

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "hmacKeys.create"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"

    @patch("requests.Session.request")
    def test_object_hmac_keys_delete(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response()

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            key = storage.hmac_key.HMACKeyMetadata(client, access_id="test key")
            key.state = storage.hmac_key.HMACKeyMetadata.INACTIVE_STATE
            key.delete()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "hmacKeys.delete"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"
        assert gcs_span.data["gcs"]["accessId"] == "test key"

    @patch("requests.Session.request")
    def test_object_hmac_keys_get(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#hmacKey", "metadata": {}, "secret": ""},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            storage.hmac_key.HMACKeyMetadata(client, access_id="test key").exists()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "hmacKeys.get"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"
        assert gcs_span.data["gcs"]["accessId"] == "test key"

    @patch("requests.Session.request")
    def test_object_hmac_keys_list(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#hmacKeysMetadata", "items": []},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            keys = client.list_hmac_keys()

            for _ in keys:
                pass

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "hmacKeys.list"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"

    @patch("requests.Session.request")
    def test_object_hmac_keys_update(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#hmacKey", "metadata": {}, "secret": ""},
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            storage.hmac_key.HMACKeyMetadata(client, access_id="test key").update()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "hmacKeys.update"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"
        assert gcs_span.data["gcs"]["accessId"] == "test key"

    @patch("requests.Session.request")
    def test_object_get_service_account_email(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={
                "email_address": "test@example.com",
                "kind": "storage#serviceAccount",
            },
            status_code=http_client.OK,
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"):
            client.get_service_account_email()

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

        current_span = get_current_span()
        assert not current_span.is_recording()

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        assert gcs_span.n == "gcs"
        assert gcs_span.k is SpanKind.CLIENT
        assert not gcs_span.ec

        assert gcs_span.data["gcs"]["op"] == "serviceAccount.get"
        assert gcs_span.data["gcs"]["projectId"] == "test-project"

    @patch("requests.Session.request")
    def test_batch_operation(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            _TWO_PART_BATCH_RESPONSE,
            status_code=http_client.OK,
            headers={"content-type": 'multipart/mixed; boundary="DEADBEEF="'},
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )
        bucket = client.bucket("test-bucket")

        with tracer.start_as_current_span("test"):
            with client.batch():
                for obj in ["obj1", "obj2"]:
                    bucket.delete_blob(obj)

        spans = self.recorder.queued_spans()

        assert len(spans) == 2

    @patch("requests.Session.request")
    def test_execute_with_instana_without_tags(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#buckets", "items": []},
            status_code=http_client.OK,
        )
        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )
        with tracer.start_as_current_span("test"), patch(
            "instana.instrumentation.google.cloud.storage._collect_attributes",
            return_value=None,
        ):
            buckets = client.list_buckets()
            for b in buckets:
                pass
            assert isinstance(buckets, page_iterator.HTTPIterator)

    def test_execute_with_instana_tracing_is_off(self) -> None:
        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )
        with tracer.start_as_current_span("test"), patch(
            "instana.instrumentation.google.cloud.storage.tracing_is_off",
            return_value=True,
        ):
            response = client.list_buckets()
            assert isinstance(response.client, storage.Client)

    @pytest.mark.skipif(
        sys.version_info >= (3, 14),
        reason='Avoiding "Fatal Python error: Segmentation fault"',
    )
    @patch("requests.Session.request")
    def test_download_with_instana_tracing_is_off(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            content=b"CONTENT", status_code=http_client.OK
        )
        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )
        with tracer.start_as_current_span("test"), patch(
            "instana.instrumentation.google.cloud.storage.tracing_is_off",
            return_value=True,
        ):
            response = (
                client.bucket("test bucket")
                .blob("test object")
                .download_to_file(
                    io.BytesIO(),
                    raw_download=True,
                )
            )
            assert not response

    @patch("requests.Session.request")
    def test_upload_with_instana_tracing_is_off(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"}, status_code=http_client.OK
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )

        with tracer.start_as_current_span("test"), patch(
            "instana.instrumentation.google.cloud.storage.tracing_is_off",
            return_value=True,
        ):
            response = (
                client.bucket("test bucket")
                .blob("test object")
                .upload_from_string("CONTENT")
            )
            assert not response

    @patch("requests.Session.request")
    def test_finish_batch_operation_tracing_is_off(self, mock_requests: Mock) -> None:
        mock_requests.return_value = self._mock_response(
            _TWO_PART_BATCH_RESPONSE,
            status_code=http_client.OK,
            headers={"content-type": 'multipart/mixed; boundary="DEADBEEF="'},
        )

        client = self._client(
            credentials=AnonymousCredentials(), project="test-project"
        )
        bucket = client.bucket("test-bucket")

        with tracer.start_as_current_span("test"), patch(
            "instana.instrumentation.google.cloud.storage.tracing_is_off",
            return_value=True,
        ):
            with client.batch() as batch_response:
                for obj in ["obj1", "obj2"]:
                    bucket.delete_blob(obj)
                assert batch_response

    def _client(self, *args, **kwargs) -> storage.Client:
        # override the HTTP client to bypass the authorization
        kwargs["_http"] = kwargs.get("_http", requests.Session())
        kwargs["_http"].is_mtls = False

        return storage.Client(*args, **kwargs)

    def _mock_response(
        self,
        content=b"",
        status_code=http_client.NO_CONTENT,
        json_content=None,
        headers={},
    ) -> Mock:
        resp = Mock()
        resp.status_code = status_code
        resp.headers = headers
        resp.content = content
        resp.__enter__ = Mock(return_value=resp)
        resp.__exit__ = Mock()

        if json_content is not None:
            if resp.content == b"":
                resp.content = json.dumps(json_content)

            resp.json = Mock(return_value=json_content)

        return resp


_TWO_PART_BATCH_RESPONSE = b"""\
--DEADBEEF=
Content-Type: application/json
Content-ID: <response-1+1>

HTTP/1.1 204 No Content

Content-Type: application/json; charset=UTF-8
Content-Length: 0

--DEADBEEF=
Content-Type: application/json
Content-ID: <response-1+2>

HTTP/1.1 204 No Content

Content-Type: application/json; charset=UTF-8
Content-Length: 0

--DEADBEEF=--
"""
