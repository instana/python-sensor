from __future__ import absolute_import

import time
import unittest

import urllib3
from instana.singletons import agent, tracer


class TestWSGI(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.http = urllib3.PoolManager()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        time.sleep(0.1)

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_requests(self):
        response = self.http.request('GET', 'http://127.0.0.1:5000/')
        spans = self.recorder.queued_spans()

        self.assertEqual(1, len(spans))
        self.assertIsNone(tracer.active_span)
        self.assertEqual(response.status, 200)

    def test_get_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', 'http://127.0.0.1:5000/')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        self.assertIsNone(tracer.active_span)

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(response)
        self.assertEqual(200, response.status)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span.error)
        self.assertIsNone(urllib3_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertIsNone(wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span.data.http.host)
        self.assertEqual('/', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual('200', wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

    def test_complex_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', 'http://127.0.0.1:5000/complex')

        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))
        self.assertIsNone(tracer.active_span)

        spacedust_span = spans[0]
        asteroid_span = spans[1]
        wsgi_span = spans[2]
        urllib3_span = spans[3]
        test_span = spans[4]

        assert(response)
        self.assertEqual(200, response.status)

        # Same traceId
        trace_id = test_span.t
        self.assertEqual(trace_id, urllib3_span.t)
        self.assertEqual(trace_id, wsgi_span.t)
        self.assertEqual(trace_id, asteroid_span.t)
        self.assertEqual(trace_id, spacedust_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)
        self.assertEqual(asteroid_span.p, wsgi_span.s)
        self.assertEqual(spacedust_span.p, asteroid_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span.error)
        self.assertIsNone(urllib3_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertIsNone(wsgi_span.ec)
        self.assertFalse(asteroid_span.error)
        self.assertIsNone(asteroid_span.ec)
        self.assertFalse(spacedust_span.error)
        self.assertIsNone(spacedust_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span.data.http.host)
        self.assertEqual('/complex', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual('200', wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

    def test_custom_header_capture(self):
        # Hack together a manual custom headers list
        agent.extra_headers = [u'X-Capture-This', u'X-Capture-That']

        request_headers = {}
        request_headers['X-Capture-This'] = 'this'
        request_headers['X-Capture-That'] = 'that'

        with tracer.start_active_span('test'):
            response = self.http.request('GET', 'http://127.0.0.1:5000/', headers=request_headers)

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        self.assertIsNone(tracer.active_span)

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(response)
        self.assertEqual(200, response.status)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span.error)
        self.assertIsNone(urllib3_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertIsNone(wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span.data.http.host)
        self.assertEqual('/', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual('200', wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        self.assertEqual(True, "http.X-Capture-This" in wsgi_span.data.custom.__dict__['tags'])
        self.assertEqual("this", wsgi_span.data.custom.__dict__['tags']["http.X-Capture-This"])
        self.assertEqual(True, "http.X-Capture-That" in wsgi_span.data.custom.__dict__['tags'])
        self.assertEqual("that", wsgi_span.data.custom.__dict__['tags']["http.X-Capture-That"])

    def test_secret_scrubbing(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', 'http://127.0.0.1:5000/?secret=shhh')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        self.assertIsNone(tracer.active_span)

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        self.assertEqual(200, response.status)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span.error)
        self.assertIsNone(urllib3_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertIsNone(wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span.data.http.host)
        self.assertEqual('/', wsgi_span.data.http.url)
        self.assertEqual('secret=<redacted>', wsgi_span.data.http.params)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual('200', wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

    def test_with_incoming_context(self):
        request_headers = {}
        request_headers['X-Instana-T'] = '1'
        request_headers['X-Instana-S'] = '1'

        response = self.http.request('GET', 'http://127.0.0.1:5000/', headers=request_headers)

        self.assertEqual(response.status, 200)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, 1)
        self.assertEqual(django_span.p, 1)

    def test_with_incoming_mixed_case_context(self):
        request_headers = {}
        request_headers['X-InSTANa-T'] = '1'
        request_headers['X-instana-S'] = '1'

        response = self.http.request('GET', 'http://127.0.0.1:5000/', headers=request_headers)

        self.assertEqual(response.status, 200)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, 1)
        self.assertEqual(django_span.p, 1)