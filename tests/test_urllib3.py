from __future__ import absolute_import
from nose.tools import assert_equals
from instana import internal_tracer as tracer
import urllib3


class TestUrllib3:
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
        assert_equals(r.status, 200)

    def test_get_request(self):
        span = tracer.start_span("test")
        r = self.http.request('GET', 'http://127.0.0.1:5000/')
        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))
        first_span = spans[1]
        second_span = spans[0]

        assert(r)
        assert_equals(200, r.status)
        assert_equals("test", first_span.data.sdk.name)
        assert_equals("urllib3", second_span.n)
        assert_equals(200, second_span.data.http.status)
        assert_equals("http://127.0.0.1:5000/", second_span.data.http.url)
        assert_equals("GET", second_span.data.http.method)

        assert_equals(None, second_span.error)
        assert_equals(None, second_span.ec)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)

    def test_put_request(self):
        span = tracer.start_span("test")
        r = self.http.request('PUT', 'http://127.0.0.1:5000/notfound')
        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))
        first_span = spans[1]
        second_span = spans[0]

        assert(r)
        assert_equals(404, r.status)
        assert_equals("test", first_span.data.sdk.name)
        assert_equals("urllib3", second_span.n)
        assert_equals(404, second_span.data.http.status)
        assert_equals("http://127.0.0.1:5000/notfound", second_span.data.http.url)
        assert_equals("PUT", second_span.data.http.method)
        assert_equals(None, second_span.error)
        assert_equals(None, second_span.ec)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)

    def test_5xx_request(self):
        span = tracer.start_span("test")
        r = self.http.request('GET', 'http://127.0.0.1:5000/504')
        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))
        first_span = spans[1]
        second_span = spans[0]

        assert(r)
        assert_equals(504, r.status)
        assert_equals("test", first_span.data.sdk.name)
        assert_equals("urllib3", second_span.n)
        assert_equals(504, second_span.data.http.status)
        assert_equals("http://127.0.0.1:5000/504", second_span.data.http.url)
        assert_equals("GET", second_span.data.http.method)
        assert_equals(True, second_span.error)
        assert_equals(1, second_span.ec)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)

    def test_exception_logging(self):
        span = tracer.start_span("test")
        try:
            r = self.http.request('GET', 'http://127.0.0.1:5000/exception')
        except Exception:
            pass

        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))
        first_span = spans[1]
        second_span = spans[0]

        assert(r)
        assert_equals(500, r.status)
        assert_equals("test", first_span.data.sdk.name)
        assert_equals("urllib3", second_span.n)
        assert_equals(500, second_span.data.http.status)
        assert_equals("http://127.0.0.1:5000/exception", second_span.data.http.url)
        assert_equals("GET", second_span.data.http.method)
        assert_equals(True, second_span.error)
        assert_equals(1, second_span.ec)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)

    def test_client_error(self):
        span = tracer.start_span("test")

        r = None
        try:
            r = self.http.request('GET', 'http://doesnotexist.asdf:5000/504',
                                  retries=False,
                                  timeout=urllib3.Timeout(connect=0.5, read=0.5))
        except Exception:
            pass

        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))
        first_span = spans[1]
        second_span = spans[0]

        assert_equals(None, r)
        assert_equals("test", first_span.data.sdk.name)
        assert_equals("urllib3", second_span.n)
        assert_equals(None, second_span.data.http.status)
        assert_equals("http://doesnotexist.asdf:5000/504", second_span.data.http.url)
        assert_equals("GET", second_span.data.http.method)
        assert_equals(True, second_span.error)
        assert_equals(1, second_span.ec)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)
