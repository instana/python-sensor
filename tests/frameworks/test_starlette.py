# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import multiprocessing
import time
import pytest
import requests
import unittest

from ..helpers import testenv
from instana.singletons import tracer
from ..helpers import get_first_span_by_filter


class TestStarlette(unittest.TestCase):
    def setUp(self):
        from tests.apps.starlette_app import launch_starlette
        self.proc = multiprocessing.Process(target=launch_starlette, args=(), daemon=True)
        self.proc.start()
        time.sleep(2)

    def tearDown(self):
        self.proc.kill() # Kill server after tests

    def test_vanilla_get(self):
        result = requests.get(testenv["starlette_server"] + '/')
        self.assertTrue(result)
        spans = tracer.recorder.queued_spans()
        # Starlette instrumentation (like all instrumentation) _always_ traces unless told otherwise
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].n, 'asgi')

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)

    def test_basic_get(self):
        result = None
        with tracer.start_active_span('test'):
            result = requests.get(testenv["starlette_server"] + '/')

        self.assertTrue(result)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        self.assertTrue(test_span.t == urllib3_span.t == asgi_span.t)
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1')
        self.assertEqual(asgi_span.data['http']['path'], '/')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 200)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

    def test_path_templates(self):
        result = None
        with tracer.start_active_span('test'):
            result = requests.get(testenv["starlette_server"] + '/users/1')

        self.assertTrue(result)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        self.assertTrue(test_span.t == urllib3_span.t == asgi_span.t)
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual( result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1')
        self.assertEqual(asgi_span.data['http']['path'], '/users/1')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/users/{user_id}')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 200)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

    def test_secret_scrubbing(self):
        result = None
        with tracer.start_active_span('test'):
            result = requests.get(testenv["starlette_server"] + '/?secret=shhh')

        self.assertTrue(result)

        spans = tracer.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        self.assertTrue(test_span.t == urllib3_span.t == asgi_span.t)
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1')
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
            result = requests.get(testenv["starlette_server"] + '/', headers=request_headers)

        self.assertTrue(result)

        spans = tracer.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        self.assertTrue(test_span.t == urllib3_span.t == asgi_span.t)
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1')
        self.assertEqual(asgi_span.data['http']['path'], '/')
        self.assertEqual(asgi_span.data['http']['path_tpl'], '/')
        self.assertEqual(asgi_span.data['http']['method'], 'GET')
        self.assertEqual(asgi_span.data['http']['status'], 200)
        self.assertIsNone(asgi_span.data['http']['error'])
        self.assertIsNone(asgi_span.data['http']['params'])

        self.assertTrue(asgi_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

    def test_custom_header_capture(self):
        from instana.singletons import agent

        # The background Starlette server is pre-configured with custom headers to capture

        request_headers = {
            'X-Capture-This': 'this',
            'X-Capture-That': 'that'
        }
        with tracer.start_active_span('test'):
            result = requests.get(testenv["starlette_server"] + '/', headers=request_headers)

        self.assertTrue(result)

        spans = tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == 'asgi'
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        self.assertTrue(test_span.t == urllib3_span.t == asgi_span.t)
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual( result.headers["X-INSTANA-S"], asgi_span.s)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual( result.headers["X-INSTANA-L"], '1')
        self.assertIn("Server-Timing", result.headers)
        self.assertEqual(result.headers["Server-Timing"], ("intid;desc=%s" % asgi_span.t))

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data['http']['host'], '127.0.0.1')
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
