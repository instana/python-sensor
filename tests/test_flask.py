from __future__ import absolute_import

import unittest

import urllib3

from instana.singletons import tracer
from .helpers import testenv


class TestFlask(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.http = urllib3.PoolManager()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_requests(self):
        r = self.http.request('GET', testenv["wsgi_server"] + '/')
        self.assertEqual(r.status, 200)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

    def test_get_request(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', testenv["wsgi_server"] + '/')

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
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data.http.host)
        self.assertEqual('/', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual(200, wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(200, urllib3_span.data.http.status)
        self.assertEqual(testenv["wsgi_server"] + '/', urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_render_template(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', testenv["wsgi_server"] + '/render')

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        render_span = spans[0]
        wsgi_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert(r)
        self.assertEqual(200, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, render_span.t)
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(test_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)
        self.assertEqual(render_span.p, wsgi_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span.error)
        self.assertIsNone(urllib3_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertIsNone(wsgi_span.ec)
        self.assertFalse(render_span.error)
        self.assertIsNone(render_span.ec)

        # render
        self.assertEqual("render", render_span.n)
        self.assertEqual(3, render_span.k)
        self.assertEqual('flask_render_template.html', render_span.data.render.name)
        self.assertEqual('template', render_span.data.render.type)
        self.assertIsNone(render_span.data.log.message)
        self.assertIsNone(render_span.data.log.parameters)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data.http.host)
        self.assertEqual('/render', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual(200, wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(200, urllib3_span.data.http.status)
        self.assertEqual(testenv["wsgi_server"] + '/render', urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_render_template_string(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', testenv["wsgi_server"] + '/render_string')

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        render_span = spans[0]
        wsgi_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert(r)
        self.assertEqual(200, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, render_span.t)
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(test_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)
        self.assertEqual(render_span.p, wsgi_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span.error)
        self.assertIsNone(urllib3_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertIsNone(wsgi_span.ec)
        self.assertFalse(render_span.error)
        self.assertIsNone(render_span.ec)

        # render
        self.assertEqual("render", render_span.n)
        self.assertEqual(3, render_span.k)
        self.assertEqual('(from string)', render_span.data.render.name)
        self.assertEqual('template', render_span.data.render.type)
        self.assertIsNone(render_span.data.log.message)
        self.assertIsNone(render_span.data.log.parameters)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data.http.host)
        self.assertEqual('/render_string', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual(200, wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(200, urllib3_span.data.http.status)
        self.assertEqual(testenv["wsgi_server"] + '/render_string', urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_301(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', testenv["wsgi_server"] + '/301', redirect=False)

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(301, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(test_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span.error)
        self.assertEqual(None, urllib3_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertEqual(None, wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data.http.host)
        self.assertEqual('/301', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual(301, wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(301, urllib3_span.data.http.status)
        self.assertEqual(testenv["wsgi_server"] + '/301', urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_404(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', testenv["wsgi_server"] + '/11111111111')

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
        self.assertEqual(test_span.t, wsgi_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, urllib3_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(urllib3_span.error)
        self.assertEqual(None, urllib3_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertEqual(None, wsgi_span.ec)

        # wsgi
        self.assertEqual("wsgi", wsgi_span.n)
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data.http.host)
        self.assertEqual('/11111111111', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual(404, wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(404, urllib3_span.data.http.status)
        self.assertEqual(testenv["wsgi_server"] + '/11111111111', urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_500(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', testenv["wsgi_server"] + '/500')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(500, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(test_span.t, wsgi_span.t)

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
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data.http.host)
        self.assertEqual('/500', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual(500, wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(500, urllib3_span.data.http.status)
        self.assertEqual(testenv["wsgi_server"] + '/500', urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_render_error(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', testenv["wsgi_server"] + '/render_error')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(500, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(test_span.t, wsgi_span.t)

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
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data.http.host)
        self.assertEqual('/render_error', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual(500, wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(500, urllib3_span.data.http.status)
        self.assertEqual(testenv["wsgi_server"] + '/render_error', urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)

    def test_exception(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', testenv["wsgi_server"] + '/exception')

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert(r)
        self.assertEqual(500, r.status)
        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(test_span.t, wsgi_span.t)

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
        self.assertEqual('127.0.0.1:' + str(testenv['wsgi_port']), wsgi_span.data.http.host)
        self.assertEqual('/exception', wsgi_span.data.http.url)
        self.assertEqual('GET', wsgi_span.data.http.method)
        self.assertEqual(500, wsgi_span.data.http.status)
        self.assertIsNone(wsgi_span.data.http.error)
        self.assertIsNotNone(wsgi_span.stack)
        self.assertEqual(2, len(wsgi_span.stack))

        # urllib3
        self.assertEqual("test", test_span.data.sdk.name)
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual(500, urllib3_span.data.http.status)
        self.assertEqual(testenv["wsgi_server"] + '/exception', urllib3_span.data.http.url)
        self.assertEqual("GET", urllib3_span.data.http.method)
        self.assertIsNotNone(urllib3_span.stack)
        self.assertTrue(type(urllib3_span.stack) is list)
        self.assertTrue(len(urllib3_span.stack) > 1)
