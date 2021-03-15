# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import unittest
import urllib3

import tests.apps.pyramid_app
from ..helpers import testenv
from instana.singletons import tracer


class TestPyramid(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.http = urllib3.PoolManager()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_requests(self):
        r = self.http.request('GET', testenv["pyramid_server"] + '/')
        self.assertEqual(r.status, 200)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

    def test_get_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', testenv["pyramid_server"] + '/')

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        self.assertEqual(200, response.status)

        assert('X-INSTANA-T' in response.headers)
        assert(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(response.headers['X-INSTANA-T'], pyramid_span.t)

        assert('X-INSTANA-S' in response.headers)
        assert(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(response.headers['X-INSTANA-S'], pyramid_span.s)

        assert('X-INSTANA-L' in response.headers)
        self.assertEqual(response.headers['X-INSTANA-L'], '1')

        assert('Server-Timing' in response.headers)
        server_timing_value = "intid;desc=%s" % pyramid_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, pyramid_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(pyramid_span.p, urllib3_span.s)

        # Synthetic
        self.assertIsNone(pyramid_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(urllib3_span.ec)
        self.assertIsNone(pyramid_span.ec)

        # HTTP SDK span
        self.assertEqual("sdk", pyramid_span.n)

        assert(pyramid_span.data["sdk"])
        self.assertEqual('http', pyramid_span.data["sdk"]["name"])
        self.assertEqual('entry', pyramid_span.data["sdk"]["type"])

        sdk_data = pyramid_span.data["sdk"]["custom"]
        self.assertEqual('127.0.0.1:' + str(testenv['pyramid_port']), sdk_data["tags"]["http.host"])
        self.assertEqual('/', sdk_data["tags"]["http.url"])
        self.assertEqual('GET', sdk_data["tags"]["http.method"])
        self.assertEqual(200, sdk_data["tags"]["http.status"])
        self.assertNotIn("message", sdk_data["tags"])
        self.assertNotIn("http.path_tpl", sdk_data["tags"])

        # urllib3
        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(200, urllib3_span.data["http"]["status"])
        self.assertEqual(testenv["pyramid_server"] + '/', urllib3_span.data["http"]["url"])
        self.assertEqual("GET", urllib3_span.data["http"]["method"])
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_synthetic_request(self):
        headers = {
            'X-INSTANA-SYNTHETIC': '1'
        }

        with tracer.start_active_span('test'):
            response = self.http.request('GET', testenv["pyramid_server"] + '/', headers=headers)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        self.assertEqual(200, response.status)

        self.assertTrue(pyramid_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

    def test_500(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', testenv["pyramid_server"] + '/500')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        self.assertEqual(500, response.status)

        assert('X-INSTANA-T' in response.headers)
        assert(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(response.headers['X-INSTANA-T'], pyramid_span.t)

        assert('X-INSTANA-S' in response.headers)
        assert(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(response.headers['X-INSTANA-S'], pyramid_span.s)

        assert('X-INSTANA-L' in response.headers)
        self.assertEqual(response.headers['X-INSTANA-L'], '1')

        assert('Server-Timing' in response.headers)
        server_timing_value = "intid;desc=%s" % pyramid_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(test_span.t, pyramid_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(pyramid_span.p, urllib3_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(1, urllib3_span.ec)
        self.assertEqual(1, pyramid_span.ec)

        # wsgi
        self.assertEqual("sdk", pyramid_span.n)
        self.assertEqual('http', pyramid_span.data["sdk"]["name"])
        self.assertEqual('entry', pyramid_span.data["sdk"]["type"])

        sdk_data = pyramid_span.data["sdk"]["custom"]
        self.assertEqual('127.0.0.1:' + str(testenv['pyramid_port']), sdk_data["tags"]["http.host"])
        self.assertEqual('/500', sdk_data["tags"]["http.url"])
        self.assertEqual('GET', sdk_data["tags"]["http.method"])
        self.assertEqual(500, sdk_data["tags"]["http.status"])
        self.assertEqual("internal error", sdk_data["tags"]["message"])
        self.assertNotIn("http.path_tpl", sdk_data["tags"])

        # urllib3
        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(500, urllib3_span.data["http"]["status"])
        self.assertEqual(testenv["pyramid_server"] + '/500', urllib3_span.data["http"]["url"])
        self.assertEqual("GET", urllib3_span.data["http"]["method"])
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_exception(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', testenv["pyramid_server"] + '/exception')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        self.assertEqual(500, response.status)

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(test_span.t, pyramid_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(pyramid_span.p, urllib3_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(1, urllib3_span.ec)
        self.assertEqual(1, pyramid_span.ec)

        # HTTP SDK span
        self.assertEqual("sdk", pyramid_span.n)
        self.assertEqual('http', pyramid_span.data["sdk"]["name"])
        self.assertEqual('entry', pyramid_span.data["sdk"]["type"])

        sdk_data = pyramid_span.data["sdk"]["custom"]
        self.assertEqual('127.0.0.1:' + str(testenv['pyramid_port']), sdk_data["tags"]["http.host"])
        self.assertEqual('/exception', sdk_data["tags"]["http.url"])
        self.assertEqual('GET', sdk_data["tags"]["http.method"])
        self.assertEqual(500, sdk_data["tags"]["http.status"])
        self.assertEqual("fake exception", sdk_data["tags"]["message"])
        self.assertNotIn("http.path_tpl", sdk_data["tags"])

        # urllib3
        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(500, urllib3_span.data["http"]["status"])
        self.assertEqual(testenv["pyramid_server"] + '/exception', urllib3_span.data["http"]["url"])
        self.assertEqual("GET", urllib3_span.data["http"]["method"])
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)
