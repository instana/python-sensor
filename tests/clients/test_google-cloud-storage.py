# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys
import unittest
import pytest
import json
import requests
import io

from instana.singletons import tracer
from ..test_utils import _TraceContextMixin

from mock import patch, Mock
from six.moves import http_client

if sys.version_info[0] >= 3:
    from google.cloud import storage
    from google.api_core import iam

@pytest.mark.skipif(sys.version_info[0] < 3, reason="google-cloud-storage has dropped support for Python 2")
class TestGoogleCloudStorage(unittest.TestCase, _TraceContextMixin):
    def setUp(self):
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    @patch('requests.Session.request')
    def test_buckets_list(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#buckets", "items": []},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            buckets = client.list_buckets()
            self.assertEqual(0, self.recorder.queue_size(), msg='span has been created before the actual request')

            # trigger the iterator
            for b in buckets:
                pass

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.list', gcs_span.data["gcs"]["op"])
        self.assertEqual('test-project', gcs_span.data["gcs"]["projectId"])

    @patch('requests.Session.request')
    def test_buckets_insert(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.create_bucket('test bucket')

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.insert', gcs_span.data["gcs"]["op"])
        self.assertEqual('test-project', gcs_span.data["gcs"]["projectId"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_buckets_get(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.get_bucket('test bucket')

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, gcs_span.t)
        self.assertEqual(test_span.s, gcs_span.p)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.get', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_buckets_patch(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').patch()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.patch', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_buckets_update(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').update()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.update', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_buckets_get_iam_policy(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#policy"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').get_iam_policy()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.getIamPolicy', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_buckets_set_iam_policy(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#policy"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').set_iam_policy(iam.Policy())

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.setIamPolicy', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_buckets_test_iam_permissions(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#testIamPermissionsResponse"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').test_iam_permissions('test-permission')

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.testIamPermissions', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_buckets_lock_retention_policy(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#bucket", "metageneration": 1, "retentionPolicy": {"isLocked": False}},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        bucket = client.bucket('test bucket')
        bucket.reload()

        with tracer.start_active_span('test'):
            bucket.lock_retention_policy()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.lockRetentionPolicy', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_buckets_delete(self, mock_requests):
        mock_requests.return_value = self._mock_response()

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').delete()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('buckets.delete', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_objects_compose(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').blob('dest object').compose([
                storage.blob.Blob('object 1', 'test bucket'),
                storage.blob.Blob('object 2', 'test bucket')
            ])

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.compose', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["destinationBucket"])
        self.assertEqual('dest object', gcs_span.data["gcs"]["destinationObject"])
        self.assertEqual('test bucket/object 1,test bucket/object 2', gcs_span.data["gcs"]["sourceObjects"])

    @patch('requests.Session.request')
    def test_objects_copy(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')
        bucket = client.bucket('src bucket')

        with tracer.start_active_span('test'):
            bucket.copy_blob(
                bucket.blob('src object'),
                client.bucket('dest bucket'),
                new_name='dest object'
            )

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.copy', gcs_span.data["gcs"]["op"])
        self.assertEqual('dest bucket', gcs_span.data["gcs"]["destinationBucket"])
        self.assertEqual('dest object', gcs_span.data["gcs"]["destinationObject"])
        self.assertEqual('src bucket', gcs_span.data["gcs"]["sourceBucket"])
        self.assertEqual('src object', gcs_span.data["gcs"]["sourceObject"])

    @patch('requests.Session.request')
    def test_objects_delete(self, mock_requests):
        mock_requests.return_value = self._mock_response()

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').blob('test object').delete()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.delete', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])
        self.assertEqual('test object', gcs_span.data["gcs"]["object"])

    @patch('requests.Session.request')
    def test_objects_attrs(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').blob('test object').exists()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.attrs', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])
        self.assertEqual('test object', gcs_span.data["gcs"]["object"])

    @patch('requests.Session.request')
    def test_objects_get(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            content=b'CONTENT',
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').blob('test object').download_to_file(
                io.BytesIO(),
                raw_download=True
            )

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.get', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])
        self.assertEqual('test object', gcs_span.data["gcs"]["object"])

    @patch('requests.Session.request')
    def test_objects_insert(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').blob('test object').upload_from_string('CONTENT')

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.insert', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])
        self.assertEqual('test object', gcs_span.data["gcs"]["object"])

    @patch('requests.Session.request')
    def test_objects_list(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            blobs = client.bucket('test bucket').list_blobs()
            self.assertEqual(0, self.recorder.queue_size(), msg='span has been created before the actual request')

            for b in blobs: pass

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.list', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_objects_patch(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').blob('test object').patch()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.patch', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])
        self.assertEqual('test object', gcs_span.data["gcs"]["object"])

    @patch('requests.Session.request')
    def test_objects_rewrite(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#rewriteResponse", "totalBytesRewritten": 0, "objectSize": 0, "done": True, "resource": {}},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('dest bucket').blob('dest object').rewrite(
                client.bucket('src bucket').blob('src object')
            )

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.rewrite', gcs_span.data["gcs"]["op"])
        self.assertEqual('dest bucket', gcs_span.data["gcs"]["destinationBucket"])
        self.assertEqual('dest object', gcs_span.data["gcs"]["destinationObject"])
        self.assertEqual('src bucket', gcs_span.data["gcs"]["sourceBucket"])
        self.assertEqual('src object', gcs_span.data["gcs"]["sourceObject"])

    @patch('requests.Session.request')
    def test_objects_update(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#object"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').blob('test object').update()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objects.update', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])
        self.assertEqual('test object', gcs_span.data["gcs"]["object"])

    @patch('requests.Session.request')
    def test_default_acls_list(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#objectAccessControls", "items": []},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').default_object_acl.get_entities()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('defaultAcls.list', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])

    @patch('requests.Session.request')
    def test_object_acls_list(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#objectAccessControls", "items": []},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.bucket('test bucket').blob('test object').acl.get_entities()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('objectAcls.list', gcs_span.data["gcs"]["op"])
        self.assertEqual('test bucket', gcs_span.data["gcs"]["bucket"])
        self.assertEqual('test object', gcs_span.data["gcs"]["object"])

    @patch('requests.Session.request')
    def test_object_hmac_keys_create(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#hmacKey", "metadata": {}, "secret": ""},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.create_hmac_key('test@example.com')

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('hmacKeys.create', gcs_span.data["gcs"]["op"])
        self.assertEqual('test-project', gcs_span.data["gcs"]["projectId"])

    @patch('requests.Session.request')
    def test_object_hmac_keys_delete(self, mock_requests):
        mock_requests.return_value = self._mock_response()

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            key = storage.hmac_key.HMACKeyMetadata(client, access_id='test key')
            key.state = storage.hmac_key.HMACKeyMetadata.INACTIVE_STATE
            key.delete()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('hmacKeys.delete', gcs_span.data["gcs"]["op"])
        self.assertEqual('test-project', gcs_span.data["gcs"]["projectId"])
        self.assertEqual('test key', gcs_span.data["gcs"]["accessId"])

    @patch('requests.Session.request')
    def test_object_hmac_keys_get(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#hmacKey", "metadata": {}, "secret": ""},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            storage.hmac_key.HMACKeyMetadata(client, access_id='test key').exists()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('hmacKeys.get', gcs_span.data["gcs"]["op"])
        self.assertEqual('test-project', gcs_span.data["gcs"]["projectId"])
        self.assertEqual('test key', gcs_span.data["gcs"]["accessId"])

    @patch('requests.Session.request')
    def test_object_hmac_keys_list(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#hmacKeysMetadata", "items": []},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            keys = client.list_hmac_keys()
            self.assertEqual(0, self.recorder.queue_size(), msg='span has been created before the actual request')

            for k in keys: pass

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('hmacKeys.list', gcs_span.data["gcs"]["op"])
        self.assertEqual('test-project', gcs_span.data["gcs"]["projectId"])

    @patch('requests.Session.request')
    def test_object_hmac_keys_update(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"kind": "storage#hmacKey", "metadata": {}, "secret": ""},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            storage.hmac_key.HMACKeyMetadata(client, access_id='test key').update()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('hmacKeys.update', gcs_span.data["gcs"]["op"])
        self.assertEqual('test-project', gcs_span.data["gcs"]["projectId"])
        self.assertEqual('test key', gcs_span.data["gcs"]["accessId"])

    @patch('requests.Session.request')
    def test_object_hmac_keys_update(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            json_content={"email_address": "test@example.com", "kind": "storage#serviceAccount"},
            status_code=http_client.OK
        )

        client = self._client(project='test-project')

        with tracer.start_active_span('test'):
            client.get_service_account_email()

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))
        self.assertIsNone(tracer.active_span)

        gcs_span = spans[0]
        test_span = spans[1]

        self.assertTraceContextPropagated(test_span, gcs_span)

        self.assertEqual('gcs',gcs_span.n)
        self.assertEqual(2, gcs_span.k)
        self.assertIsNone(gcs_span.ec)

        self.assertEqual('serviceAccount.get', gcs_span.data["gcs"]["op"])
        self.assertEqual('test-project', gcs_span.data["gcs"]["projectId"])

    @patch('requests.Session.request')
    def test_batch_operation(self, mock_requests):
        mock_requests.return_value = self._mock_response(
            _TWO_PART_BATCH_RESPONSE,
            status_code=http_client.OK,
            headers={"content-type": 'multipart/mixed; boundary="DEADBEEF="'}
        )

        client = self._client(project='test-project')
        bucket = client.bucket('test-bucket')

        with tracer.start_active_span('test'):
            with client.batch():
                for obj in ['obj1', 'obj2']:
                    bucket.delete_blob(obj)

        spans = self.recorder.queued_spans()

        self.assertEqual(2, len(spans))

    def _client(self, *args, **kwargs):
        # override the HTTP client to bypass the authorization
        kwargs['_http'] = kwargs.get('_http', requests.Session())
        kwargs['_http'].is_mtls = False

        return storage.Client(*args, **kwargs)

    def _mock_response(self, content=b'', status_code=http_client.NO_CONTENT, json_content=None, headers={}):
        resp = Mock()
        resp.status_code = status_code
        resp.headers = headers
        resp.content = content
        resp.__enter__ = Mock(return_value=resp)
        resp.__exit__ = Mock()

        if json_content is not None:
            if resp.content == b'':
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
