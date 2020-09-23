from __future__ import absolute_import

import unittest

from instana.instrumentation.google.cloud.storage import collect_tags

class TestGoogleCloudStorage(unittest.TestCase):
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
            )
        }

        for (op, (request, expected)) in test_cases.items():
            self.assertEqual(expected, collect_tags(request), msg=op)
