# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os

import urllib3
from django.apps import apps
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from ..apps.app_django import INSTALLED_APPS
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
        """ Clear the INSTANA_DISABLE_W3C_TRACE_CORRELATION environment variable """
        os.environ["INSTANA_DISABLE_W3C_TRACE_CORRELATION"] = ""

    def test_basic_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/', fields={"test": 1})

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-INSTANA-T'])

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-INSTANA-S'])

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual('1', response.headers['X-INSTANA-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        self.assertIn('Server-Timing', response.headers)
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
        self.assertEqual('test=1', django_span.data["http"]["params"])
        self.assertEqual('^$', django_span.data["http"]["path_tpl"])

        self.assertIsNone(django_span.stack)

    def test_synthetic_request(self):
        headers = {
            'X-INSTANA-SYNTHETIC': '1'
        }

        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/', headers=headers)

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        self.assertEqual('^$', django_span.data["http"]["path_tpl"])

        self.assertTrue(django_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

    def test_request_with_error(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/cause_error')

        self.assertTrue(response)
        self.assertEqual(500, response.status)

        spans = self.recorder.queued_spans()
        spans = drop_log_spans_from_list(spans)

        span_count = len(spans)
        if span_count != 3:
            msg = "Expected 3 spans but got %d" % span_count
            fail_with_message_and_span_dump(msg, spans)

        filter = lambda span: span.n == 'sdk' and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(test_span)

        filter = lambda span: span.n == 'urllib3'
        urllib3_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(urllib3_span)

        filter = lambda span: span.n == 'django'
        django_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(django_span)

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-INSTANA-T'])

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-INSTANA-S'])

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual('1', response.headers['X-INSTANA-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        self.assertIn('Server-Timing', response.headers)
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
        self.assertEqual('^cause_error$', django_span.data["http"]["path_tpl"])
        self.assertIsNone(django_span.stack)

    def test_request_with_not_found(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/not_found')

        self.assertTrue(response)
        self.assertEqual(404, response.status)

        spans = self.recorder.queued_spans()
        spans = drop_log_spans_from_list(spans)

        span_count = len(spans)
        if span_count != 3:
            msg = "Expected 3 spans but got %d" % span_count
            fail_with_message_and_span_dump(msg, spans)

        filter = lambda span: span.n == 'django'
        django_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(django_span)

        self.assertIsNone(django_span.ec)
        self.assertEqual(404, django_span.data["http"]["status"])

    def test_request_with_not_found_no_route(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/no_route')

        self.assertTrue(response)
        self.assertEqual(404, response.status)

        spans = self.recorder.queued_spans()
        spans = drop_log_spans_from_list(spans)

        span_count = len(spans)
        if span_count != 3:
            msg = "Expected 3 spans but got %d" % span_count
            fail_with_message_and_span_dump(msg, spans)

        filter = lambda span: span.n == 'django'
        django_span = get_first_span_by_filter(spans, filter)
        self.assertTrue(django_span)
        self.assertIsNone(django_span.data["http"]["path_tpl"])
        self.assertIsNone(django_span.ec)
        self.assertEqual(404, django_span.data["http"]["status"])

    def test_complex_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/complex')

        self.assertTrue(response)
        self.assertEqual(200, response.status)
        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))

        test_span = spans[4]
        urllib3_span = spans[3]
        django_span = spans[2]
        ot_span1 = spans[1]
        ot_span2 = spans[0]

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-INSTANA-T'])

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-INSTANA-S'])

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual('1', response.headers['X-INSTANA-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        self.assertIn('Server-Timing', response.headers)
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
        self.assertIsNone(django_span.stack)

        self.assertEqual('/complex', django_span.data["http"]["url"])
        self.assertEqual('GET', django_span.data["http"]["method"])
        self.assertEqual(200, django_span.data["http"]["status"])
        self.assertEqual('^complex$', django_span.data["http"]["path_tpl"])

    def test_request_header_capture(self):
        # Hack together a manual custom headers list
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

        request_headers = {
            'X-Capture-This': 'this',
            'X-Capture-That': 'that'
        }

        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)
            # response = self.client.get('/')

        self.assertTrue(response)
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
        self.assertIsNone(django_span.stack)

        self.assertEqual('/', django_span.data["http"]["url"])
        self.assertEqual('GET', django_span.data["http"]["method"])
        self.assertEqual(200, django_span.data["http"]["status"])
        self.assertEqual('^$', django_span.data["http"]["path_tpl"])

        self.assertIn("X-Capture-This", django_span.data["http"]["header"])
        self.assertEqual("this", django_span.data["http"]["header"]["X-Capture-This"])
        self.assertIn("X-Capture-That", django_span.data["http"]["header"])
        self.assertEqual("that", django_span.data["http"]["header"]["X-Capture-That"])

        agent.options.extra_http_headers = original_extra_http_headers

    def test_response_header_capture(self):
        # Hack together a manual custom headers list
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = [u'X-Capture-This-Too', u'X-Capture-That-Too']

        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/response_with_headers')

        self.assertTrue(response)
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
        self.assertIsNone(django_span.stack)

        self.assertEqual('/response_with_headers', django_span.data["http"]["url"])
        self.assertEqual('GET', django_span.data["http"]["method"])
        self.assertEqual(200, django_span.data["http"]["status"])
        self.assertEqual('^response_with_headers$', django_span.data["http"]["path_tpl"])

        self.assertIn("X-Capture-This-Too", django_span.data["http"]["header"])
        self.assertEqual("this too", django_span.data["http"]["header"]["X-Capture-This-Too"])
        self.assertIn("X-Capture-That-Too", django_span.data["http"]["header"])
        self.assertEqual("that too", django_span.data["http"]["header"]["X-Capture-That-Too"])

        agent.options.extra_http_headers = original_extra_http_headers

    def test_with_incoming_context(self):
        request_headers = dict()
        request_headers['X-INSTANA-T'] = '1'
        request_headers['X-INSTANA-S'] = '1'
        request_headers['traceparent'] = '01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01-788777'
        request_headers['tracestate'] = 'rojo=00f067aa0ba902b7,in=a3ce929d0e0e4736;8357ccd9da194656,congo=t61rcWkgMzE'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, '0000000000000001')
        self.assertEqual(django_span.p, '0000000000000001')

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-INSTANA-T'])

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-INSTANA-S'])

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual('1', response.headers['X-INSTANA-L'])

        self.assertIn('traceparent', response.headers)
        # The incoming traceparent header had version 01 (which does not exist at the time of writing), but since we
        # support version 00, we also need to pass down 00 for the version field.
        self.assertEqual('00-4bf92f3577b34da6a3ce929d0e0e4736-{}-01'.format(django_span.s),
                         response.headers['traceparent'])

        self.assertIn('tracestate', response.headers)
        self.assertEqual(
            'in={};{},rojo=00f067aa0ba902b7,congo=t61rcWkgMzE'.format(
                django_span.t, django_span.s), response.headers['tracestate'])
        server_timing_value = "intid;desc=%s" % django_span.t
        self.assertIn('Server-Timing', response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

    def test_with_incoming_context_and_correlation(self):
        request_headers = dict()
        request_headers['X-INSTANA-T'] = '1'
        request_headers['X-INSTANA-S'] = '1'
        request_headers['X-INSTANA-L'] = '1, correlationType=web; correlationId=1234567890abcdef'
        request_headers['traceparent'] = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        request_headers['tracestate'] = 'rojo=00f067aa0ba902b7,in=a3ce929d0e0e4736;8357ccd9da194656,congo=t61rcWkgMzE'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, 'a3ce929d0e0e4736')
        self.assertEqual(django_span.p, '00f067aa0ba902b7')
        self.assertEqual(django_span.ia.t, 'a3ce929d0e0e4736')
        self.assertEqual(django_span.ia.p, '8357ccd9da194656')
        self.assertEqual(django_span.lt, '4bf92f3577b34da6a3ce929d0e0e4736')
        self.assertEqual(django_span.tp, True)
        self.assertEqual(django_span.crtp, 'web')
        self.assertEqual(django_span.crid, '1234567890abcdef')

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-INSTANA-T'])

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-INSTANA-S'])

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual('1', response.headers['X-INSTANA-L'])

        self.assertIn('traceparent', response.headers)
        self.assertEqual('00-4bf92f3577b34da6a3ce929d0e0e4736-{}-01'.format(django_span.s),
                         response.headers['traceparent'])

        self.assertIn('tracestate', response.headers)
        self.assertEqual(
            'in={};{},rojo=00f067aa0ba902b7,congo=t61rcWkgMzE'.format(
                django_span.t, django_span.s), response.headers['tracestate'])

        server_timing_value = "intid;desc=%s" % django_span.t
        self.assertIn('Server-Timing', response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

    def test_with_incoming_traceparent_tracestate(self):
        request_headers = dict()
        request_headers['traceparent'] = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        request_headers['tracestate'] = 'rojo=00f067aa0ba902b7,in=a3ce929d0e0e4736;8357ccd9da194656,congo=t61rcWkgMzE'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, 'a3ce929d0e0e4736')  # last 16 chars from traceparent trace_id
        self.assertEqual(django_span.p, '00f067aa0ba902b7')
        self.assertEqual(django_span.ia.t, 'a3ce929d0e0e4736')
        self.assertEqual(django_span.ia.p, '8357ccd9da194656')
        self.assertEqual(django_span.lt, '4bf92f3577b34da6a3ce929d0e0e4736')
        self.assertEqual(django_span.tp, True)

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-INSTANA-T'])

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-INSTANA-S'])

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual('1', response.headers['X-INSTANA-L'])

        self.assertIn('traceparent', response.headers)
        self.assertEqual('00-4bf92f3577b34da6a3ce929d0e0e4736-{}-01'.format(django_span.s),
                         response.headers['traceparent'])

        self.assertIn('tracestate', response.headers)
        self.assertEqual(
            'in=a3ce929d0e0e4736;{},rojo=00f067aa0ba902b7,congo=t61rcWkgMzE'.format(
                django_span.s), response.headers['tracestate'])

        server_timing_value = "intid;desc=%s" % django_span.t
        self.assertIn('Server-Timing', response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

    def test_with_incoming_traceparent_tracestate_disable_traceparent(self):
        os.environ["INSTANA_DISABLE_W3C_TRACE_CORRELATION"] = "1"
        request_headers = dict()
        request_headers['traceparent'] = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        request_headers['tracestate'] = 'rojo=00f067aa0ba902b7,in=a3ce929d0e0e4736;8357ccd9da194656,congo=t61rcWkgMzE'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, 'a3ce929d0e0e4736')  # last 16 chars from traceparent trace_id
        self.assertEqual(django_span.p, '8357ccd9da194656')

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-INSTANA-T'])

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-INSTANA-S'])

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual('1', response.headers['X-INSTANA-L'])

        self.assertIn('traceparent', response.headers)
        self.assertEqual('00-4bf92f3577b34da6a3ce929d0e0e4736-{}-01'.format(django_span.s),
                         response.headers['traceparent'])

        self.assertIn('tracestate', response.headers)
        self.assertEqual(
            'in={};{},rojo=00f067aa0ba902b7,congo=t61rcWkgMzE'.format(
                django_span.t, django_span.s), response.headers['tracestate'])

        server_timing_value = "intid;desc=%s" % django_span.t
        self.assertIn('Server-Timing', response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])

    def test_with_incoming_mixed_case_context(self):
        request_headers = dict()
        request_headers['X-InSTANa-T'] = '0000000000000001'
        request_headers['X-instana-S'] = '0000000000000001'

        response = self.http.request('GET', self.live_server_url + '/', headers=request_headers)

        self.assertTrue(response)
        self.assertEqual(200, response.status)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

        django_span = spans[0]

        self.assertEqual(django_span.t, '0000000000000001')
        self.assertEqual(django_span.p, '0000000000000001')

        self.assertIn('X-INSTANA-T', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-T'], 16))
        self.assertEqual(django_span.t, response.headers['X-INSTANA-T'])

        self.assertIn('X-INSTANA-S', response.headers)
        self.assertTrue(int(response.headers['X-INSTANA-S'], 16))
        self.assertEqual(django_span.s, response.headers['X-INSTANA-S'])

        self.assertIn('X-INSTANA-L', response.headers)
        self.assertEqual('1', response.headers['X-INSTANA-L'])

        server_timing_value = "intid;desc=%s" % django_span.t
        self.assertIn('Server-Timing', response.headers)
        self.assertEqual(server_timing_value, response.headers['Server-Timing'])
