from __future__ import absolute_import

import urllib3
from django.apps import apps
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from nose.tools import assert_equals

from instana.singletons import agent, tracer

from .apps.app_django import INSTALLED_APPS

apps.populate(INSTALLED_APPS)


class TestDjango(StaticLiveServerTestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.http = urllib3.PoolManager()

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_basic_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/')

        assert response
        assert_equals(200, response.status)

        spans = self.recorder.queued_spans()
        assert_equals(3, len(spans))

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        assert ('X-Instana-T' in response.headers)
        assert (int(response.headers['X-Instana-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-Instana-T'])

        assert ('X-Instana-S' in response.headers)
        assert (int(response.headers['X-Instana-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-Instana-S'])

        assert ('X-Instana-L' in response.headers)
        assert_equals('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

        assert_equals("test", test_span.data.sdk.name)
        assert_equals("urllib3", urllib3_span.n)
        assert_equals("django", django_span.n)

        assert_equals(test_span.t, urllib3_span.t)
        assert_equals(urllib3_span.t, django_span.t)

        assert_equals(urllib3_span.p, test_span.s)
        assert_equals(django_span.p, urllib3_span.s)

        assert_equals(None, django_span.error)
        assert_equals(None, django_span.ec)

        assert_equals('/', django_span.data.http.url)
        assert_equals('GET', django_span.data.http.method)
        assert_equals(200, django_span.data.http.status)
        assert django_span.stack
        assert_equals(2, len(django_span.stack))

    def test_request_with_error(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/cause_error')

        assert response
        assert_equals(500, response.status)

        spans = self.recorder.queued_spans()
        assert_equals(3, len(spans))

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        assert ('X-Instana-T' in response.headers)
        assert (int(response.headers['X-Instana-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-Instana-T'])

        assert ('X-Instana-S' in response.headers)
        assert (int(response.headers['X-Instana-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-Instana-S'])

        assert ('X-Instana-L' in response.headers)
        assert_equals('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

        assert_equals("test", test_span.data.sdk.name)
        assert_equals("urllib3", urllib3_span.n)
        assert_equals("django", django_span.n)

        assert_equals(test_span.t, urllib3_span.t)
        assert_equals(urllib3_span.t, django_span.t)

        assert_equals(urllib3_span.p, test_span.s)
        assert_equals(django_span.p, urllib3_span.s)

        assert_equals(True, django_span.error)
        assert_equals(1, django_span.ec)

        assert_equals('/cause_error', django_span.data.http.url)
        assert_equals('GET', django_span.data.http.method)
        assert_equals(500, django_span.data.http.status)
        assert_equals('This is a fake error: /cause-error', django_span.data.http.error)
        assert(django_span.stack)
        assert_equals(2, len(django_span.stack))

    def test_complex_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/complex')

        assert response
        assert_equals(200, response.status)
        spans = self.recorder.queued_spans()
        assert_equals(5, len(spans))

        test_span = spans[4]
        urllib3_span = spans[3]
        django_span = spans[2]
        ot_span1 = spans[1]
        ot_span2 = spans[0]

        assert ('X-Instana-T' in response.headers)
        assert (int(response.headers['X-Instana-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-Instana-T'])

        assert ('X-Instana-S' in response.headers)
        assert (int(response.headers['X-Instana-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-Instana-S'])

        assert ('X-Instana-L' in response.headers)
        assert_equals('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

        assert_equals("test", test_span.data.sdk.name)
        assert_equals("urllib3", urllib3_span.n)
        assert_equals("django", django_span.n)
        assert_equals("sdk", ot_span1.n)
        assert_equals("sdk", ot_span2.n)

        assert_equals(test_span.t, urllib3_span.t)
        assert_equals(urllib3_span.t, django_span.t)
        assert_equals(django_span.t, ot_span1.t)
        assert_equals(ot_span1.t, ot_span2.t)

        assert_equals(urllib3_span.p, test_span.s)
        assert_equals(django_span.p, urllib3_span.s)
        assert_equals(ot_span1.p, django_span.s)
        assert_equals(ot_span2.p, ot_span1.s)

        assert_equals(None, django_span.error)
        assert_equals(None, django_span.ec)
        assert(django_span.stack)
        assert_equals(2, len(django_span.stack))

        assert_equals('/complex', django_span.data.http.url)
        assert_equals('GET', django_span.data.http.method)
        assert_equals(200, django_span.data.http.status)

    def test_custom_header_capture(self):
        # Hack together a manual custom headers list
        agent.extra_headers = [u'X-Capture-This', u'X-Capture-That']

        request_headers = dict()
        request_headers['X-Capture-This'] = 'this'
        request_headers['X-Capture-That'] = 'that'

        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)
            # response = self.client.get('/')

        assert response
        assert_equals(200, response.status)

        spans = self.recorder.queued_spans()
        assert_equals(3, len(spans))

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        assert_equals("test", test_span.data.sdk.name)
        assert_equals("urllib3", urllib3_span.n)
        assert_equals("django", django_span.n)

        assert_equals(test_span.t, urllib3_span.t)
        assert_equals(urllib3_span.t, django_span.t)

        assert_equals(urllib3_span.p, test_span.s)
        assert_equals(django_span.p, urllib3_span.s)

        assert_equals(None, django_span.error)
        assert_equals(None, django_span.ec)
        assert(django_span.stack)
        assert_equals(2, len(django_span.stack))

        assert_equals('/', django_span.data.http.url)
        assert_equals('GET', django_span.data.http.method)
        assert_equals(200, django_span.data.http.status)

        assert_equals(True, "http.X-Capture-This" in django_span.data.custom.__dict__['tags'])
        assert_equals("this", django_span.data.custom.__dict__['tags']["http.X-Capture-This"])
        assert_equals(True, "http.X-Capture-That" in django_span.data.custom.__dict__['tags'])
        assert_equals("that", django_span.data.custom.__dict__['tags']["http.X-Capture-That"])

    def test_with_incoming_context(self):
        request_headers = dict()
        request_headers['X-Instana-T'] = '1'
        request_headers['X-Instana-S'] = '1'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        assert response
        assert_equals(200, response.status)

        spans = self.recorder.queued_spans()
        assert_equals(1, len(spans))

        django_span = spans[0]

        assert_equals(django_span.t, '0000000000000001')
        assert_equals(django_span.p, '0000000000000001')

        assert ('X-Instana-T' in response.headers)
        assert (int(response.headers['X-Instana-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-Instana-T'])

        assert ('X-Instana-S' in response.headers)
        assert (int(response.headers['X-Instana-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-Instana-S'])

        assert ('X-Instana-L' in response.headers)
        assert_equals('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

    def test_with_incoming_mixed_case_context(self):
        request_headers = dict()
        request_headers['X-InSTANa-T'] = '0000000000000001'
        request_headers['X-instana-S'] = '0000000000000001'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        assert response
        assert_equals(200, response.status)

        spans = self.recorder.queued_spans()
        assert_equals(1, len(spans))

        django_span = spans[0]

        assert_equals(django_span.t, '0000000000000001')
        assert_equals(django_span.p, '0000000000000001')

        assert ('X-Instana-T' in response.headers)
        assert (int(response.headers['X-Instana-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-Instana-T'])

        assert ('X-Instana-S' in response.headers)
        assert (int(response.headers['X-Instana-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-Instana-S'])

        assert ('X-Instana-L' in response.headers)
        assert_equals('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])
