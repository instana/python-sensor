# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import time
import requests
import multiprocessing
import unittest

from instana.singletons import tracer
from ..helpers import testenv
from ..helpers import get_first_span_by_filter
from ..test_utils import _TraceContextMixin


class TestSanic(unittest.TestCase, _TraceContextMixin):
    def setUp(self):
        from tests.apps.sanic_app import launch_sanic
        self.proc = multiprocessing.Process(target=launch_sanic, args=(), daemon=True)
        self.proc.start()
        time.sleep(2)

    def tearDown(self):
        """ Kill server after tests """
        self.proc.kill()

    def test_vanilla_get(self):
        result = requests.get(testenv["sanic_server"] + '/')

        self.assertEqual(result.status_code, 200)
        self.assertIn("X-INSTANA-T", result.headers)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")
        self.assertIn("Server-Timing", result.headers)
        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].n, 'asgi')

    def test_basic_get(self):
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/')

        self.assertEqual(result.status_code, 200)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 200)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

    def test_404(self):
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/foo/not_an_int')

        self.assertEqual(result.status_code, 404)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/foo/not_an_int')
        self.assertIsNone(asgi_span.data['http']['path_tpl'])
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 404)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

    def test_sanic_exception(self):
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/wrong')

        self.assertEqual(result.status_code, 400)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/wrong')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/wrong')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 400)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

    def test_500_instana_exception(self):
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/instana_exception')

        self.assertEqual(result.status_code, 500)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 4)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertEqual(asgi_span.ec, 1)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/instana_exception')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/instana_exception')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 500)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

    def test_500(self):
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/test_request_args')

        self.assertEqual(result.status_code, 500)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 4)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertEqual(asgi_span.ec, 1)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/test_request_args')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/test_request_args')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 500)
        self.assertEqual(asgi_span.data['http']['error'], 'Something went wrong.')
        self.assertIsNone(asgi_span.data['http']['params'])

    def test_path_templates(self):
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/foo/1')

        self.assertEqual(result.status_code, 200)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/foo/1')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/foo/<foo_id:int>')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 200)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

    def test_secret_scrubbing(self):
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/?secret=shhh')

        self.assertEqual(result.status_code, 200)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 200)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertEqual(asgi_span.data['http']['params'], 'secret=<redacted>')

    def test_synthetic_request(self):
        request_headers = {
            'X-INSTANA-SYNTHETIC': '1'
        }
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/', headers=request_headers)

        self.assertEqual(result.status_code, 200)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 200)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

        self.assertIsNotNone(asgi_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

    def test_request_header_capture(self):
        request_headers = {
            'X-Capture-This': 'this',
            'X-Capture-That': 'that'
        }
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/', headers=request_headers)

        self.assertEqual(result.status_code, 200)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['http']['path'], '/')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 200)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

        self.assertIn("X-Capture-This", asgi_span.data["http"]["header"])
        self.assertEqual("this", asgi_span.data["http"]["header"]["X-Capture-This"])
        self.assertIn("X-Capture-That", asgi_span.data["http"]["header"])
        self.assertEqual("that", asgi_span.data["http"]["header"]["X-Capture-That"])

    def test_response_header_capture(self):
        with tracer.start_active_span("test"):
            result = requests.get(testenv["sanic_server"] + "/response_headers")

        self.assertEqual(result.status_code, 200)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(asgi_span)

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data["http"]["path"], "/response_headers")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/response_headers")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 200)

        self.assertIsNone(asgi_span.data["http"]["error"])
        self.assertIsNone(asgi_span.data["http"]["params"])

        self.assertIn("X-Capture-This-Too", asgi_span.data["http"]["header"])
        self.assertEqual("this too", asgi_span.data["http"]["header"]["X-Capture-This-Too"])
        self.assertIn("X-Capture-That-Too", asgi_span.data["http"]["header"])
        self.assertEqual("that too", asgi_span.data["http"]["header"]["X-Capture-That-Too"])
