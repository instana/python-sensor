from __future__ import absolute_import

import urllib3
from django.apps import apps
from ..apps.app_django import INSTALLED_APPS
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from instana.singletons import agent, tracer

from ..helpers import fail_with_message_and_span_dump, get_first_span_by_filter, drop_log_spans_from_list

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
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

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
        self.assertEqual('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual("django", django_span.n)

        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, django_span.t)

        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(django_span.p, urllib3_span.s)

        self.assertIsNone(django_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

        self.assertEqual(None, django_span.ec)

        self.assertEqual('/', django_span.data["http"]["url"])
        self.assertEqual('GET', django_span.data["http"]["method"])
        self.assertEqual(200, django_span.data["http"]["status"])
        assert django_span.stack
        self.assertEqual(2, len(django_span.stack))

    def test_synthetic_request(self):
        headers = {
            'X-Instana-Synthetic': '1'
        }
        
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/', headers=headers)

        assert response
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        self.assertTrue(django_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

    def test_request_with_error(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/cause_error')

        assert response
        self.assertEqual(500, response.status)

        spans = self.recorder.queued_spans()
        spans = drop_log_spans_from_list(spans)

        span_count = len(spans)
        if span_count != 3:
            msg = "Expected 3 spans but got %d" % span_count
            fail_with_message_and_span_dump(msg, spans)

        filter = lambda span: span.n == 'sdk' and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, filter)
        assert(test_span)

        filter = lambda span: span.n == 'urllib3'
        urllib3_span = get_first_span_by_filter(spans, filter)
        assert(urllib3_span)

        filter = lambda span: span.n == 'django'
        django_span = get_first_span_by_filter(spans, filter)
        assert(django_span)

        assert ('X-Instana-T' in response.headers)
        assert (int(response.headers['X-Instana-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-Instana-T'])

        assert ('X-Instana-S' in response.headers)
        assert (int(response.headers['X-Instana-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-Instana-S'])

        assert ('X-Instana-L' in response.headers)
        self.assertEqual('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual("django", django_span.n)

        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, django_span.t)

        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(django_span.p, urllib3_span.s)

        self.assertEqual(1, django_span.ec)

        self.assertEqual('/cause_error', django_span.data["http"]["url"])
        self.assertEqual('GET', django_span.data["http"]["method"])
        self.assertEqual(500, django_span.data["http"]["status"])
        self.assertEqual('This is a fake error: /cause-error', django_span.data["http"]["error"])
        assert(django_span.stack)
        self.assertEqual(2, len(django_span.stack))

    def test_complex_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/complex')

        assert response
        self.assertEqual(200, response.status)
        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))

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
        self.assertEqual('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual("django", django_span.n)
        self.assertEqual("sdk", ot_span1.n)
        self.assertEqual("sdk", ot_span2.n)

        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, django_span.t)
        self.assertEqual(django_span.t, ot_span1.t)
        self.assertEqual(ot_span1.t, ot_span2.t)

        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(django_span.p, urllib3_span.s)
        self.assertEqual(ot_span1.p, django_span.s)
        self.assertEqual(ot_span2.p, ot_span1.s)

        self.assertEqual(None, django_span.ec)
        assert(django_span.stack)
        self.assertEqual(2, len(django_span.stack))

        self.assertEqual('/complex', django_span.data["http"]["url"])
        self.assertEqual('GET', django_span.data["http"]["method"])
        self.assertEqual(200, django_span.data["http"]["status"])

    def test_custom_header_capture(self):
        # Hack together a manual custom headers list
        agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

        request_headers = dict()
        request_headers['X-Capture-This'] = 'this'
        request_headers['X-Capture-That'] = 'that'

        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)
            # response = self.client.get('/')

        assert response
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual("urllib3", urllib3_span.n)
        self.assertEqual("django", django_span.n)

        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, django_span.t)

        self.assertEqual(urllib3_span.p, test_span.s)
        self.assertEqual(django_span.p, urllib3_span.s)

        self.assertEqual(None, django_span.ec)
        assert(django_span.stack)
        self.assertEqual(2, len(django_span.stack))

        self.assertEqual('/', django_span.data["http"]["url"])
        self.assertEqual('GET', django_span.data["http"]["method"])
        self.assertEqual(200, django_span.data["http"]["status"])

        self.assertEqual(True, "http.X-Capture-This" in django_span.data["custom"]['tags'])
        self.assertEqual("this", django_span.data["custom"]['tags']["http.X-Capture-This"])
        self.assertEqual(True, "http.X-Capture-That" in django_span.data["custom"]['tags'])
        self.assertEqual("that", django_span.data["custom"]['tags']["http.X-Capture-That"])

    def test_with_incoming_context(self):
        request_headers = dict()
        request_headers['X-Instana-T'] = '1'
        request_headers['X-Instana-S'] = '1'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        assert response
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, '0000000000000001')
        self.assertEqual(django_span.p, '0000000000000001')

        assert ('X-Instana-T' in response.headers)
        assert (int(response.headers['X-Instana-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-Instana-T'])

        assert ('X-Instana-S' in response.headers)
        assert (int(response.headers['X-Instana-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-Instana-S'])

        assert ('X-Instana-L' in response.headers)
        self.assertEqual('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

    def test_with_incoming_mixed_case_context(self):
        request_headers = dict()
        request_headers['X-InSTANa-T'] = '0000000000000001'
        request_headers['X-instana-S'] = '0000000000000001'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        assert response
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, '0000000000000001')
        self.assertEqual(django_span.p, '0000000000000001')

        assert ('X-Instana-T' in response.headers)
        assert (int(response.headers['X-Instana-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-Instana-T'])

        assert ('X-Instana-S' in response.headers)
        assert (int(response.headers['X-Instana-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-Instana-S'])

        assert ('X-Instana-L' in response.headers)
        self.assertEqual('1', response.headers['X-Instana-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        assert ('Server-Timing' in response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])
