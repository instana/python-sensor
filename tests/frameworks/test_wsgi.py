# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
import urllib3
import unittest

from tests.apps import bottle_app
from tests.helpers import testenv
from instana.singletons import agent, tracer
from instana.span.span import get_current_span


class TestWSGI(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.http = urllib3.PoolManager()
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        time.sleep(0.1)

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_requests(self):
        response = self.http.request('GET', testenv["wsgi_server"] + '/')
        spans = self.recorder.queued_spans()

        self.assertEqual(1, len(spans))
        assert get_current_span().is_recording() is False
        self.assertEqual(response.status, 200)

    def test_get_request(self):
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        assert response.headers["X-INSTANA-T"] == str(wsgi_span.t)

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        assert response.headers["X-INSTANA-S"] == str(wsgi_span.s)

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual(response.headers['X-INSTANA-L'], '1')

        self.assertIn('Server-Timing', response.headers)
        server_timing_value = "intid;desc=%s" % wsgi_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        self.assertIsNone(wsgi_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(urllib3_span.ec)
        self.assertIsNone(wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data["http"]["host"])
        self.assertEqual('/', wsgi_span.data["http"]["path"])
        self.assertEqual('GET', wsgi_span.data["http"]["method"])
        self.assertEqual("200", wsgi_span.data["http"]["status"])
        self.assertIsNone(wsgi_span.data["http"]["error"])
        self.assertIsNone(wsgi_span.stack)

    @unittest.skip("Suppression is not yet handled")
    def test_synthetic_request(self):
        headers = {
            'X-INSTANA-SYNTHETIC': '1'
        }
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/', headers=headers)

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        self.assertTrue(wsgi_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)


    def test_custom_header_capture(self):
        # Hack together a manual custom headers list
        agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

        request_headers = {}
        request_headers['X-Capture-This'] = 'this'
        request_headers['X-Capture-That'] = 'that'

        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/', headers=request_headers)

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        assert response.headers["X-INSTANA-T"] == str(wsgi_span.t)

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        assert response.headers["X-INSTANA-S"] == str(wsgi_span.s)

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual(response.headers['X-INSTANA-L'], '1')

        self.assertIn('Server-Timing', response.headers)
        server_timing_value = "intid;desc=%s" % wsgi_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(urllib3_span.ec)
        self.assertIsNone(wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data["http"]["host"])
        self.assertEqual('/', wsgi_span.data["http"]["path"])
        self.assertEqual('GET', wsgi_span.data["http"]["method"])
        self.assertEqual("200", wsgi_span.data["http"]["status"])
        self.assertIsNone(wsgi_span.data["http"]["error"])
        self.assertIsNone(wsgi_span.stack)

        self.assertIn("X-Capture-This", wsgi_span.data["http"]["header"])
        self.assertEqual("this", wsgi_span.data["http"]["header"]["X-Capture-This"])
        self.assertIn("X-Capture-That", wsgi_span.data["http"]["header"])
        self.assertEqual("that", wsgi_span.data["http"]["header"]["X-Capture-That"])

    def test_secret_scrubbing(self):
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/?secret=shhh')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        assert response.headers["X-INSTANA-T"] == str(wsgi_span.t)

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        assert response.headers["X-INSTANA-S"] == str(wsgi_span.s)

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual(response.headers['X-INSTANA-L'], '1')

        self.assertIn('Server-Timing', response.headers)
        server_timing_value = "intid;desc=%s" % wsgi_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(urllib3_span.ec)
        self.assertIsNone(wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data["http"]["host"])
        self.assertEqual('/', wsgi_span.data["http"]["path"])
        self.assertEqual('secret=<redacted>', wsgi_span.data["http"]["params"])
        self.assertEqual('GET', wsgi_span.data["http"]["method"])
        self.assertEqual("200", wsgi_span.data["http"]["status"])
        self.assertIsNone(wsgi_span.data["http"]["error"])
        self.assertIsNone(wsgi_span.stack)

    def test_with_incoming_context(self):
        request_headers = dict()
        request_headers['X-INSTANA-T'] = '0000000000000001'
        request_headers['X-INSTANA-S'] = '0000000000000001'

        response = self.http.request('GET', testenv["wsgi_server"] + '/', headers=request_headers)

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        wsgi_span = spans[0]

        # self.assertEqual(wsgi_span.t, '0000000000000001')
        # self.assertEqual(wsgi_span.p, '0000000000000001')
        assert wsgi_span.t == 1
        assert wsgi_span.p == 1

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        assert response.headers["X-INSTANA-T"] == str(wsgi_span.t)

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        assert response.headers["X-INSTANA-S"] == str(wsgi_span.s)

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual(response.headers['X-INSTANA-L'], '1')

        self.assertIn('Server-Timing', response.headers)
        server_timing_value = "intid;desc=%s" % wsgi_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)

    def test_with_incoming_mixed_case_context(self):
        request_headers = dict()
        request_headers['X-InSTANa-T'] = '0000000000000001'
        request_headers['X-instana-S'] = '0000000000000001'

        response = self.http.request('GET', testenv["wsgi_server"] + '/', headers=request_headers)

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        wsgi_span = spans[0]

        # self.assertEqual(wsgi_span.t, '0000000000000001')
        # self.assertEqual(wsgi_span.p, '0000000000000001')
        assert wsgi_span.t == 1
        assert wsgi_span.p == 1

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        assert response.headers["X-INSTANA-T"] == str(wsgi_span.t)

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        assert response.headers["X-INSTANA-S"] == str(wsgi_span.s)

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual(response.headers['X-INSTANA-L'], '1')

        self.assertIn('Server-Timing', response.headers)
        server_timing_value = "intid;desc=%s" % wsgi_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)

    def test_response_headers(self):
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        assert response.headers["X-INSTANA-T"] == str(wsgi_span.t)

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        assert response.headers["X-INSTANA-S"] == str(wsgi_span.s)

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual(response.headers['X-INSTANA-L'], '1')

        self.assertIn('Server-Timing', response.headers)
        server_timing_value = "intid;desc=%s" % wsgi_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)
