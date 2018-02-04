from __future__ import absolute_import
from nose.tools import assert_equals
from instana import internal_tracer as tracer
from instana.util import to_json
import requests
import urllib3


class TestUrllib3:
    def setUp(self):
        """ Clear all spans before a test run """
        self.http = urllib3.PoolManager()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        tracer.cur_ctx = None

    def tearDown(self):
        """ Do nothing for now """
        # after each test, tracer context should be None (not tracing)
        assert_equals(None, tracer.current_context())
        return None

    def test_vanilla_requests(self):
        r = self.http.request('GET', 'http://127.0.0.1:5000/')
        assert_equals(r.status, 200)

        spans = self.recorder.queued_spans()
        assert_equals(0, len(spans))

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

        assert_equals(None, tracer.current_context())

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

        assert_equals(None, tracer.current_context())

    def test_301_redirect(self):
        span = tracer.start_span("test")
        r = self.http.request('GET', 'http://127.0.0.1:5000/301')
        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(3, len(spans))
        first_span = spans[2]
        second_span = spans[1]
        third_span = spans[0]

        assert(r)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)

        assert_equals(third_span.t, first_span.t)
        assert_equals(third_span.p, first_span.s)

        assert(first_span.d)
        assert(second_span.d)
        assert(third_span.d)

    def test_302_redirect(self):
        span = tracer.start_span("test")
        r = self.http.request('GET', 'http://127.0.0.1:5000/302')
        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(3, len(spans))
        first_span = spans[2]
        second_span = spans[1]
        third_span = spans[0]

        assert(r)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)

        assert_equals(third_span.t, first_span.t)
        assert_equals(third_span.p, first_span.s)

        assert(first_span.d)
        assert(second_span.d)
        assert(third_span.d)

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

    def test_requestspkg_get(self):
        span = tracer.start_span("test")
        r = requests.get('http://127.0.0.1:5000/', timeout=2)
        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))
        first_span = spans[1]
        second_span = spans[0]

        assert(r)
        assert_equals(200, r.status_code)
        assert_equals("test", first_span.data.sdk.name)
        assert_equals("urllib3", second_span.n)
        assert_equals(200, second_span.data.http.status)
        assert_equals("http://127.0.0.1:5000/", second_span.data.http.url)
        assert_equals("GET", second_span.data.http.method)

        assert_equals(None, second_span.error)
        assert_equals(None, second_span.ec)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)

    def test_requestspkg_put(self):
        span = tracer.start_span("test")
        r = requests.put('http://127.0.0.1:5000/notfound')
        span.finish()

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))
        first_span = spans[1]
        second_span = spans[0]

        assert_equals(404, r.status_code)
        assert_equals("test", first_span.data.sdk.name)
        assert_equals("urllib3", second_span.n)
        assert_equals(404, second_span.data.http.status)
        assert_equals("http://127.0.0.1:5000/notfound", second_span.data.http.url)
        assert_equals("PUT", second_span.data.http.method)
        assert_equals(None, second_span.error)
        assert_equals(None, second_span.ec)

        assert_equals(second_span.t, first_span.t)
        assert_equals(second_span.p, first_span.s)
