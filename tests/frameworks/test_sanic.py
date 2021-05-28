# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from __future__ import absolute_import

import time
import pytest
import requests
import multiprocessing
from instana.singletons import tracer
from ..helpers import testenv
from ..helpers import get_first_span_by_filter
from ..test_utils import _TraceContextMixin
import sys
import unittest


@pytest.mark.skipif(sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 7),
                    reason="testing sanic for python 3.7 and up")
class TestSanic(unittest.TestCase, _TraceContextMixin):

    def setUp(self):
        from tests.apps.sanic_app import launch_sanic
        self.proc = multiprocessing.Process(target=launch_sanic, args=(), daemon=True)
        self.proc.start()
        time.sleep(2)

    def tearDown(self):
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
        self.assertEqual(spans[0].n, 'sdk')

    def test_basic_get(self):
        result = None
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

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
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
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path'], '/')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'], '/')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.method'], 'GET')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.status_code'], 200)
        self.assertNotIn('http.error', asgi_span.data['sdk']['custom']['tags'])
        self.assertNotIn('http.params', asgi_span.data['sdk']['custom']['tags'])

    def test_404(self):
        result = None
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

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
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
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path'], '/foo/not_an_int')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.method'], 'GET')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.status_code'], 404)
        self.assertNotIn('http.error', asgi_span.data['sdk']['custom']['tags'])
        self.assertNotIn('http.params', asgi_span.data['sdk']['custom']['tags'])
        self.assertNotIn('http.path_tpl', asgi_span.data['sdk']['custom']['tags'])

    def test_500(self):
        result = None
        with tracer.start_active_span('test'):
            result = requests.get(testenv["sanic_server"] + '/test_request_args')

        self.assertEqual(result.status_code, 500)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertIsNotNone(urllib3_span)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
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
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path'], '/test_request_args')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'], '/test_request_args')

        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.method'], 'GET')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.status_code'], 500)
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.error'], 'Something went wrong.')
        self.assertNotIn('http.params', asgi_span.data['sdk']['custom']['tags'])

    def test_path_templates(self):
        result = None
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

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
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
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path'], '/foo/1')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'], '/foo/<foo_id:int>')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.method'], 'GET')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.status_code'], 200)
        self.assertNotIn('http.error', asgi_span.data['sdk']['custom']['tags'])
        self.assertNotIn('http.params', asgi_span.data['sdk']['custom']['tags'])

    def test_secret_scrubbing(self):
        result = None
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

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
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
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path'], '/')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'], '/')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.method'], 'GET')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.status_code'], 200)
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.params'], 'secret=<redacted>')
        self.assertNotIn('http.error', asgi_span.data['sdk']['custom']['tags'])

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

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
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
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path'], '/')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'], '/')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.method'], 'GET')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.status_code'], 200)
        self.assertNotIn('http.error', asgi_span.data['sdk']['custom']['tags'])
        self.assertNotIn('http.params', asgi_span.data['sdk']['custom']['tags'])

        self.assertIsNotNone(asgi_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

    def test_custom_header_capture(self):
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

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
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
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.host'], '127.0.0.1:1337')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path'], '/')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'], '/')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.method'], 'GET')
        self.assertEqual(asgi_span.data['sdk']['custom']['tags']['http.status_code'], 200)
        self.assertNotIn('http.error', asgi_span.data['sdk']['custom']['tags'])
        self.assertNotIn('http.params', asgi_span.data['sdk']['custom']['tags'])

        self.assertIn("http.header.X-Capture-This", asgi_span.data["sdk"]["custom"]['tags'])
        self.assertEqual("this", asgi_span.data["sdk"]["custom"]['tags']["http.header.X-Capture-This"])
        self.assertIn("http.header.X-Capture-That", asgi_span.data["sdk"]["custom"]['tags'])
        self.assertEqual("that", asgi_span.data["sdk"]["custom"]['tags']["http.header.X-Capture-That"])
