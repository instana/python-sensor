from __future__ import absolute_import

import unittest

import requests
import urllib3

from instana.singletons import tracer


class TestUrllib3(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.http = urllib3.PoolManager()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_requests(self):
        r = self.http.request('GET', 'http://127.0.0.1:5000/')
        self.assertEqual(r.status, 200)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

    def test_get_request(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/')

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(200, r.status)
        self.assertIsNone(tracer.active_span)

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

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(200, urllib3_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/", urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_get_request_with_query(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/?one=1&two=2')

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(200, r.status)
        self.assertIsNone(tracer.active_span)

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

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(200, urllib3_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/", urllib3_span.data.http.url)
        self.assertEqual("one=1&two=2", urllib3_span.data.http.params)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_get_request_with_alt_query(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/', fields={'one': '1', 'two': 2})

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(200, r.status)
        self.assertIsNone(tracer.active_span)

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

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(200, urllib3_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/", urllib3_span.data.http.url)
        self.assertEqual("one=1&two=2", urllib3_span.data.http.params)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_put_request(self):
        with tracer.start_active_span('test'):
            r = self.http.request('PUT', 'http://127.0.0.1:5000/notfound')

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(404, r.status)
        self.assertIsNone(tracer.active_span)

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
        self.assertEqual('/notfound', wsgi_span.data.http.url)
        self.assertEqual('PUT', wsgi_span.data.http.method)
        self.assertEqual('404', wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(404, urllib3_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/notfound", urllib3_span.data.http.url)
        self.assertEqual("PUT", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_301_redirect(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/301')

        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))

        wsgi_span2 = spans[0]
        urllib3_span2 = spans[1]
        wsgi_span1 = spans[2]
        urllib3_span1 = spans[3]
        test_span = spans[4]

        assert(r)
        self.assertEqual(200, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, urllib3_span1.t)
        self.assertEqual(traceId, wsgi_span1.t)
        self.assertEqual(traceId, urllib3_span2.t)
        self.assertEqual(traceId, wsgi_span2.t)

        # Parent relationships
        self.assertEqual(urllib3_span1.p, test_span.s)
        self.assertEqual(wsgi_span1.p, urllib3_span1.s)
        self.assertEqual(urllib3_span2.p, test_span.s)
        self.assertEqual(wsgi_span2.p, urllib3_span2.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span1.error)
        self.assertIsNone(urllib3_span1.ec)
        self.assertFalse(wsgi_span1.error)
        self.assertIsNone(wsgi_span1.ec)
        self.assertFalse(urllib3_span2.error)
        self.assertIsNone(urllib3_span2.ec)
        self.assertFalse(wsgi_span2.error)
        self.assertIsNone(wsgi_span2.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span1.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span1.data.http.host)
        self.assertEqual('/', wsgi_span1.data.http.url)
        self.assertEqual('GET', wsgi_span1.data.http.method)
        self.assertEqual('200', wsgi_span1.data.http.status)
        self.assertIsNone(wsgi_span1.data.http.error)
        self.assertIsNotNone(wsgi_span1.stack)
        self.assertEqual(2, len(wsgi_span1.stack))

        self.assertEqual("wsgi", wsgi_span2.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span2.data.http.host)
        self.assertEqual('/301', wsgi_span2.data.http.url)
        self.assertEqual('GET', wsgi_span2.data.http.method)
        self.assertEqual('301', wsgi_span2.data.http.status)
        self.assertIsNone(wsgi_span2.data.http.error)
        self.assertIsNotNone(wsgi_span2.stack)
        self.assertEqual(2, len(wsgi_span2.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span1.n)
        self.assertEqual(200, urllib3_span1.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/", urllib3_span1.data.http.url)
        self.assertEqual("GET", urllib3_span1.data.http.method)
        self.assertIsNotNone(urllib3_span1.stack)
        self.assertTrue(type(urllib3_span1.stack) is list)
        self.assertTrue(len(urllib3_span1.stack) > 1)

        self.assertEqual("urllib3", urllib3_span2.n)
        self.assertEqual(301, urllib3_span2.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/301", urllib3_span2.data.http.url)
        self.assertEqual("GET", urllib3_span2.data.http.method)
        self.assertIsNotNone(urllib3_span2.stack)
        self.assertTrue(type(urllib3_span2.stack) is list)
        self.assertTrue(len(urllib3_span2.stack) > 1)

    def test_302_redirect(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/302')

        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))

        wsgi_span2 = spans[0]
        urllib3_span2 = spans[1]
        wsgi_span1 = spans[2]
        urllib3_span1 = spans[3]
        test_span = spans[4]

        assert(r)
        self.assertEqual(200, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, urllib3_span1.t)
        self.assertEqual(traceId, wsgi_span1.t)
        self.assertEqual(traceId, urllib3_span2.t)
        self.assertEqual(traceId, wsgi_span2.t)

        # Parent relationships
        self.assertEqual(urllib3_span1.p, test_span.s)
        self.assertEqual(wsgi_span1.p, urllib3_span1.s)
        self.assertEqual(urllib3_span2.p, test_span.s)
        self.assertEqual(wsgi_span2.p, urllib3_span2.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span1.error)
        self.assertIsNone(urllib3_span1.ec)
        self.assertFalse(wsgi_span1.error)
        self.assertIsNone(wsgi_span1.ec)
        self.assertFalse(urllib3_span2.error)
        self.assertIsNone(urllib3_span2.ec)
        self.assertFalse(wsgi_span2.error)
        self.assertIsNone(wsgi_span2.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span1.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span1.data.http.host)
        self.assertEqual('/', wsgi_span1.data.http.url)
        self.assertEqual('GET', wsgi_span1.data.http.method)
        self.assertEqual('200', wsgi_span1.data.http.status)
        self.assertIsNone(wsgi_span1.data.http.error)
        self.assertIsNotNone(wsgi_span1.stack)
        self.assertEqual(2, len(wsgi_span1.stack))

        self.assertEqual("wsgi", wsgi_span2.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span2.data.http.host)
        self.assertEqual('/302', wsgi_span2.data.http.url)
        self.assertEqual('GET', wsgi_span2.data.http.method)
        self.assertEqual('302', wsgi_span2.data.http.status)
        self.assertIsNone(wsgi_span2.data.http.error)
        self.assertIsNotNone(wsgi_span2.stack)
        self.assertEqual(2, len(wsgi_span2.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span1.n)
        self.assertEqual(200, urllib3_span1.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/", urllib3_span1.data.http.url)
        self.assertEqual("GET", urllib3_span1.data.http.method)
        self.assertIsNotNone(urllib3_span1.stack)
        self.assertTrue(type(urllib3_span1.stack) is list)
        self.assertTrue(len(urllib3_span1.stack) > 1)

        self.assertEqual("urllib3", urllib3_span2.n)
        self.assertEqual(302, urllib3_span2.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/302", urllib3_span2.data.http.url)
        self.assertEqual("GET", urllib3_span2.data.http.method)
        self.assertIsNotNone(urllib3_span2.stack)
        self.assertTrue(type(urllib3_span2.stack) is list)
        self.assertTrue(len(urllib3_span2.stack) > 1)

    def test_5xx_request(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/504')

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(504, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, urllib3_span.t)
        self.assertEqual(traceId, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertTrue(urllib3_span.error)
        self.assertEqual(1, urllib3_span.ec)
        self.assertTrue(wsgi_span.error)
        self.assertEqual(1, wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span.data.http.host)
        self.assertEqual('/504', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual('504', wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(504, urllib3_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/504", urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_exception_logging(self):
        with tracer.start_active_span('test'):
            try:
                r = self.http.request('GET', 'http://127.0.0.1:5000/exception')
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(500, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, urllib3_span.t)
        self.assertEqual(traceId, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertTrue(urllib3_span.error)
        self.assertEqual(1, urllib3_span.ec)
        self.assertTrue(wsgi_span.error)
        self.assertEqual(1, wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:5000', wsgi_span.data.http.host)
        self.assertEqual('/exception', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual('500', wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(500, urllib3_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/exception", urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_client_error(self):
        r = None
        with tracer.start_active_span('test'):
            try:
                r = self.http.request('GET', 'http://doesnotexist.asdf:5000/504',
                                      retries=False,
                                      timeout=urllib3.Timeout(connect=0.5, read=0.5))
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        urllib3_span = spans[0]
        test_span = spans[1]

        self.assertIsNone(r)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, urllib3_span.t)

        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertIsNone(urllib3_span.data.http.status)
        self.assertEqual("http://doesnotexist.asdf:5000/504", urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertTrue(urllib3_span.error)
        self.assertEqual(1, urllib3_span.ec)

    def test_requestspkg_get(self):
        with tracer.start_active_span('test'):
            r = requests.get('http://127.0.0.1:5000/', timeout=2)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(200, r.status_code)
        self.assertIsNone(tracer.active_span)

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

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(200, urllib3_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/", urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_requestspkg_put(self):
        with tracer.start_active_span('test'):
            r = requests.put('http://127.0.0.1:5000/notfound')

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        self.assertEqual(404, r.status_code)
        self.assertIsNone(tracer.active_span)

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
        self.assertEqual('/notfound', wsgi_span.data.http.url)
        self.assertEqual('PUT', wsgi_span.data.http.method)
        self.assertEqual('404', wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(404, urllib3_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/notfound", urllib3_span.data.http.url)
        self.assertEqual("PUT", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)
