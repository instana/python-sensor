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

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_requests(self):
        r = self.http.request('GET', 'http://127.0.0.1:5000/')
        assert_equals(r.status, 200)

        spans = self.recorder.queued_spans()
        assert_equals(0, len(spans))

    def test_get_request(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/')

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

        assert_equals(None, tracer.active_span)

    def test_put_request(self):
        with tracer.start_active_span('test'):
            r = self.http.request('PUT', 'http://127.0.0.1:5000/notfound')

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

        assert_equals(None, tracer.active_span)

    def test_301_redirect(self):
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/301')

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
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/302')

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
        with tracer.start_active_span('test'):
            r = self.http.request('GET', 'http://127.0.0.1:5000/504')

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
        with tracer.start_active_span('test'):
            try:
                r = self.http.request('GET', 'http://127.0.0.1:5000/exception')
            except Exception:
                pass

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
        with tracer.start_active_span('test'):
            try:
                r = self.http.request('GET', 'http://doesnotexist.asdf:5000/504',
                                      retries=False,
                                      timeout=urllib3.Timeout(connect=0.5, read=0.5))
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        import pdb; pdb.Pdb(skip=['django.*']).set_trace()
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
        with tracer.start_active_span('test'):
            r = requests.get('http://127.0.0.1:5000/', timeout=2)

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
        with tracer.start_active_span('test'):
            r = requests.put('http://127.0.0.1:5000/notfound')

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
