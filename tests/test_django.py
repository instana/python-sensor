from __future__ import absolute_import

import urllib3
from django.apps import apps
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from instana.tracer import internal_tracer as tracer
from nose.tools import assert_equals

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
            # response = self.client.get('/')

        assert_equals(response.status, 200)

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
        assert_equals(0, django_span.ec)

        assert_equals('/', django_span.data.http.url)
        assert_equals('GET', django_span.data.http.method)
        assert_equals(200, django_span.data.http.status)

    def test_request_with_error(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/cause_error')
            # response = self.client.get('/')

        assert_equals(response.status, 500)

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

        assert_equals(True, django_span.error)
        assert_equals(1, django_span.ec)

        assert_equals('/cause_error', django_span.data.http.url)
        assert_equals('GET', django_span.data.http.method)
        assert_equals(500, django_span.data.http.status)
        assert_equals('This is a fake error: /cause-error', django_span.data.http.error)

    def test_complex_request(self):
        with tracer.start_active_span('test'):
            response = self.http.request('GET', self.live_server_url + '/complex')

        assert_equals(response.status, 200)

        spans = self.recorder.queued_spans()
        assert_equals(5, len(spans))

        test_span = spans[4]
        urllib3_span = spans[3]
        django_span = spans[2]
        ot_span1 = spans[1]
        ot_span2 = spans[0]

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
        assert_equals(0, django_span.ec)

        assert_equals('/complex', django_span.data.http.url)
        assert_equals('GET', django_span.data.http.method)
        assert_equals(200, django_span.data.http.status)
