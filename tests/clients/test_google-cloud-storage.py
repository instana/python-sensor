from __future__ import absolute_import

import unittest

from instana.instrumentation.google.cloud.storage import collect_tags

class TestGoogleCloudStorage(unittest.TestCase):
    class Blob:
        def __init__(self, name):
            self.name = name

    def test_collect_tags(self):
        test_cases = {
            'buckets.list': (
                {
                    'method': 'GET',
                    'path': '/b',
                    'query_params': {'project': 'test-project'}
                },
                {
                    'gcs.op': 'buckets.list',
                    'gcs.projectId': 'test-project'
                }
            ),
            'buckets.insert':(
                {
                    'method': 'POST',
                    'path': '/b',
                    'query_params': {'project': 'test-project'},
                    'data': {'name': 'test bucket'}
                },
                {
                    'gcs.op': 'buckets.insert',
                    'gcs.projectId': 'test-project',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'buckets.get': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket'
                },
                {
                    'gcs.op': 'buckets.get',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'buckets.patch': (
                {
                    'method': 'PATCH',
                    'path': '/b/test%20bucket'
                },
                {
                    'gcs.op': 'buckets.patch',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'buckets.update': (
                {
                    'method': 'PUT',
                    'path': '/b/test%20bucket'
                },
                {
                    'gcs.op': 'buckets.update',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'buckets.getIamPolicy': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/iam'
                },
                {
                    'gcs.op': 'buckets.getIamPolicy',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'buckets.setIamPolicy': (
                {
                    'method': 'PUT',
                    'path': '/b/test%20bucket/iam'
                },
                {
                    'gcs.op': 'buckets.setIamPolicy',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'buckets.testIamPermissions': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/iam/testPermissions'
                },
                {
                    'gcs.op': 'buckets.testIamPermissions',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'buckets.lockRetentionPolicy': (
                {
                    'method': 'POST',
                    'path': '/b/test%20bucket/lockRetentionPolicy'
                },
                {
                    'gcs.op': 'buckets.lockRetentionPolicy',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'buckets.delete': (
                {
                    'method': 'PUT',
                    'path': '/b/test%20bucket'
                },
                {
                    'gcs.op': 'buckets.update',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'objects.compose': (
                {
                    'method': 'POST',
                    'path': '/b/test%20bucket/o/dest%20object/compose',
                    'data': {
                        'sourceObjects': [
                            TestGoogleCloudStorage.Blob('object1'),
                            TestGoogleCloudStorage.Blob('object2'),
                        ]
                    }
                },
                {
                    'gcs.op': 'objects.compose',
                    'gcs.destinationBucket': 'test bucket',
                    'gcs.destinationObject': 'dest object',
                    'gcs.sourceObjects': 'test bucket/object1,test bucket/object2'
                }
            ),
            'objects.copy': (
                {
                    'method': 'POST',
                    'path': '/b/src%20bucket/o/src%20object/copyTo/b/dest%20bucket/o/dest%20object'
                },
                {
                    'gcs.op': 'objects.copy',
                    'gcs.destinationBucket': 'dest bucket',
                    'gcs.destinationObject': 'dest object',
                    'gcs.sourceBucket': 'src bucket',
                    'gcs.sourceObject': 'src object'
                }
            ),
            'objects.delete': (
                {
                    'method': 'DELETE',
                    'path': '/b/test%20bucket/o/test%20object'
                },
                {
                    'gcs.op': 'objects.delete',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object'
                }
            ),
            'objects.attrs': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/o/test%20object'
                },
                {
                    'gcs.op': 'objects.attrs',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object'
                }
            ),
            'objects.get': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/o/test%20object',
                    'query_params': {'alt': 'media'}
                },
                {
                    'gcs.op': 'objects.get',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object'
                }
            ),
            'objects.insert': (
                {
                    'method': 'POST',
                    'path': '/b/test%20bucket/o',
                    'query_params': {'name': 'test object'}
                },
                {
                    'gcs.op': 'objects.insert',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object'
                }
            ),
            'objects.list': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/o'
                },
                {
                    'gcs.op': 'objects.list',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'objects.patch': (
                {
                    'method': 'PATCH',
                    'path': '/b/test%20bucket/o/test%20object'
                },
                {
                    'gcs.op': 'objects.patch',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object'
                }
            ),
            'objects.rewrite': (
                {
                    'method': 'POST',
                    'path': '/b/src%20bucket/o/src%20object/rewriteTo/b/dest%20bucket/o/dest%20object'
                },
                {
                    'gcs.op': 'objects.rewrite',
                    'gcs.destinationBucket': 'dest bucket',
                    'gcs.destinationObject': 'dest object',
                    'gcs.sourceBucket': 'src bucket',
                    'gcs.sourceObject': 'src object'
                }
            ),
            'objects.update': (
                {
                    'method': 'PUT',
                    'path': '/b/test%20bucket/o/test%20object'
                },
                {
                    'gcs.op': 'objects.update',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object'
                }
            ),
            'channels.stop': (
                {
                    'method': 'POST',
                    'path': '/channels/stop',
                    'data': {'id': 'test channel'}
                },
                {
                    'gcs.op': 'channels.stop',
                    'gcs.entity': 'test channel'
                }
            ),
            'defaultAcls.delete': (
                {
                    'method': 'DELETE',
                    'path': '/b/test%20bucket/defaultObjectAcl/user-test%40example.com'
                },
                {
                    'gcs.op': 'defaultAcls.delete',
                    'gcs.bucket': 'test bucket',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'defaultAcls.get': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/defaultObjectAcl/user-test%40example.com'
                },
                {
                    'gcs.op': 'defaultAcls.get',
                    'gcs.bucket': 'test bucket',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'defaultAcls.insert': (
                {
                    'method': 'POST',
                    'path': '/b/test%20bucket/defaultObjectAcl',
                    'data': {'entity': 'user-test@example.com'}
                },
                {
                    'gcs.op': 'defaultAcls.insert',
                    'gcs.bucket': 'test bucket',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'defaultAcls.list': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/defaultObjectAcl'
                },
                {
                    'gcs.op': 'defaultAcls.list',
                    'gcs.bucket': 'test bucket'
                }
            ),
            'defaultAcls.patch': (
                {
                    'method': 'PATCH',
                    'path': '/b/test%20bucket/defaultObjectAcl/user-test%40example.com'
                },
                {
                    'gcs.op': 'defaultAcls.patch',
                    'gcs.bucket': 'test bucket',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'defaultAcls.update': (
                {
                    'method': 'PUT',
                    'path': '/b/test%20bucket/defaultObjectAcl/user-test%40example.com'
                },
                {
                    'gcs.op': 'defaultAcls.update',
                    'gcs.bucket': 'test bucket',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'objectAcls.delete': (
                {
                    'method': 'DELETE',
                    'path': '/b/test%20bucket/o/test%20object/acl/user-test%40example.com'
                },
                {
                    'gcs.op': 'objectAcls.delete',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'objectAcls.get': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/o/test%20object/acl/user-test%40example.com'
                },
                {
                    'gcs.op': 'objectAcls.get',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'objectAcls.insert': (
                {
                    'method': 'POST',
                    'path': '/b/test%20bucket/o/test%20object/acl',
                    'data': {'entity': 'user-test@example.com'}
                },
                {
                    'gcs.op': 'objectAcls.insert',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'objectAcls.list': (
                {
                    'method': 'GET',
                    'path': '/b/test%20bucket/o/test%20object/acl'
                },
                {
                    'gcs.op': 'objectAcls.list',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object'
                }
            ),
            'objectAcls.patch': (
                {
                    'method': 'PATCH',
                    'path': '/b/test%20bucket/o/test%20object/acl/user-test%40example.com'
                },
                {
                    'gcs.op': 'objectAcls.patch',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object',
                    'gcs.entity': 'user-test@example.com'
                }
            ),
            'objectAcls.update': (
                {
                    'method': 'PUT',
                    'path': '/b/test%20bucket/o/test%20object/acl/user-test%40example.com'
                },
                {
                    'gcs.op': 'objectAcls.update',
                    'gcs.bucket': 'test bucket',
                    'gcs.object': 'test object',
                    'gcs.entity': 'user-test@example.com'
                }
            )
        }

        for (op, (request, expected)) in test_cases.items():
            self.assertEqual(expected, collect_tags(request), msg=op)
