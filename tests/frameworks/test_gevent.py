from __future__ import absolute_import

import os
import pytest
import gevent
from gevent.pool import Group
import urllib3
import unittest

import tests.apps.flask_app
from instana.span import SDKSpan
from instana.singletons import tracer
from ..helpers import testenv, get_spans_by_filter
from opentracing.scope_managers.gevent import GeventScopeManager


@pytest.mark.skipif("GEVENT_TEST" not in os.environ, reason="")
class TestGEvent(unittest.TestCase):
    def setUp(self):
        self.http = urllib3.HTTPConnectionPool('127.0.0.1', port=testenv["wsgi_port"], maxsize=20)
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        tracer._scope_manager = GeventScopeManager()

    def tearDown(self):
        """ Do nothing for now """
        pass

    def make_http_call(self, n=None):
        return self.http.request('GET', testenv["wsgi_server"] + '/')

    def spawn_calls(self):
        with tracer.start_active_span('spawn_calls'):
            jobs = []
            jobs.append(gevent.spawn(self.make_http_call))
            jobs.append(gevent.spawn(self.make_http_call))
            jobs.append(gevent.spawn(self.make_http_call))
            gevent.joinall(jobs, timeout=2)

    def spawn_imap_unordered(self):
        igroup = Group()
        result = []
        with tracer.start_active_span('test'):
            for i in igroup.imap_unordered(self.make_http_call, range(3)):
                result.append(i)

    def launch_gevent_chain(self):
        with tracer.start_active_span('test'):
            gevent.spawn(self.spawn_calls).join()

    def test_spawning(self):
        gevent.spawn(self.launch_gevent_chain)

        gevent.sleep(2)

        spans = self.recorder.queued_spans()

        self.assertEqual(8, len(spans))

        span_filter = lambda span: span.n == "sdk" \
                                   and span.data['sdk']['name'] == 'test' and span.p == None
        test_spans = get_spans_by_filter(spans, span_filter)
        self.assertIsNotNone(test_spans)
        self.assertEqual(len(test_spans), 1)

        test_span = test_spans[0]
        self.assertTrue(type(test_spans[0]) is SDKSpan)

        span_filter = lambda span: span.n == "sdk" \
                                   and span.data['sdk']['name'] == 'spawn_calls' and span.p == test_span.s
        spawn_spans = get_spans_by_filter(spans, span_filter)
        self.assertIsNotNone(spawn_spans)
        self.assertEqual(len(spawn_spans), 1)

        spawn_span = spawn_spans[0]
        self.assertTrue(type(spawn_spans[0]) is SDKSpan)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_spans = get_spans_by_filter(spans, span_filter)

        for urllib3_span in urllib3_spans:
            # spans should all have the same test span parent
            self.assertEqual(urllib3_span.t, spawn_span.t)
            self.assertEqual(urllib3_span.p, spawn_span.s)

            # find the wsgi span generated from this urllib3 request
            span_filter = lambda span: span.n == "wsgi" and span.p == urllib3_span.s
            wsgi_spans = get_spans_by_filter(spans, span_filter)
            self.assertIsNotNone(wsgi_spans)
            self.assertEqual(len(wsgi_spans), 1)

    def test_imap_unordered(self):
        gevent.spawn(self.spawn_imap_unordered())

        gevent.sleep(2)

        spans = self.recorder.queued_spans()
        self.assertEqual(7, len(spans))

        span_filter = lambda span: span.n == "sdk" \
                                   and span.data['sdk']['name'] == 'test' and span.p == None
        test_spans = get_spans_by_filter(spans, span_filter)
        self.assertIsNotNone(test_spans)
        self.assertEqual(len(test_spans), 1)

        test_span = test_spans[0]
        self.assertTrue(type(test_spans[0]) is SDKSpan)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_spans = get_spans_by_filter(spans, span_filter)
        self.assertEqual(len(urllib3_spans), 3)

        for urllib3_span in urllib3_spans:
            # spans should all have the same test span parent
            self.assertEqual(urllib3_span.t, test_span.t)
            self.assertEqual(urllib3_span.p, test_span.s)

            # find the wsgi span generated from this urllib3 request
            span_filter = lambda span: span.n == "wsgi" and span.p == urllib3_span.s
            wsgi_spans = get_spans_by_filter(spans, span_filter)
            self.assertIsNotNone(wsgi_spans)
            self.assertEqual(len(wsgi_spans), 1)

