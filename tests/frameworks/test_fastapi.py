# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
import unittest
import multiprocessing

import requests

from instana.singletons import async_tracer
from tests.apps.fastapi_app import launch_fastapi
from ..helpers import testenv
from ..helpers import get_first_span_by_filter


class TestFastAPI(unittest.TestCase):
    def setUp(self):
        self.proc = multiprocessing.Process(target=launch_fastapi, args=(), daemon=True)
        self.proc.start()
        time.sleep(2)

    def tearDown(self):
        # Kill server after tests
        self.proc.kill()

    def test_vanilla_get(self):
        result = requests.get(testenv["fastapi_server"] + "/")

        self.assertEqual(result.status_code, 200)
        self.assertIn("X-INSTANA-T", result.headers)
        self.assertIn("X-INSTANA-S", result.headers)
        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")
        self.assertIn("Server-Timing", result.headers)

        spans = async_tracer.recorder.queued_spans()
        # FastAPI instrumentation (like all instrumentation) _always_ traces unless told otherwise
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].n, "asgi")

    def test_basic_get(self):
        result = None
        with async_tracer.start_active_span("test"):
            result = requests.get(testenv["fastapi_server"] + "/")

        self.assertEqual(result.status_code, 200)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span.data["http"]["path"], "/")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 200)

        self.assertIsNone(asgi_span.data["http"]["error"])
        self.assertIsNone(asgi_span.data["http"]["params"])

    def test_400(self):
        result = None
        with async_tracer.start_active_span("test"):
            result = requests.get(testenv["fastapi_server"] + "/400")

        self.assertEqual(result.status_code, 400)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span.data["http"]["path"], "/400")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/400")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 400)

        self.assertIsNone(asgi_span.data["http"]["error"])
        self.assertIsNone(asgi_span.data["http"]["params"])

    def test_500(self):
        result = None
        with async_tracer.start_active_span("test"):
            result = requests.get(testenv["fastapi_server"] + "/500")

        self.assertEqual(result.status_code, 500)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertEqual(asgi_span.ec, 1)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span.data["http"]["path"], "/500")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/500")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 500)
        self.assertEqual(asgi_span.data["http"]["error"], "500 response")

        self.assertIsNone(asgi_span.data["http"]["params"])

    def test_path_templates(self):
        result = None
        with async_tracer.start_active_span("test"):
            result = requests.get(testenv["fastapi_server"] + "/users/1")

        self.assertEqual(result.status_code, 200)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span.data["http"]["path"], "/users/1")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/users/{user_id}")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 200)

        self.assertIsNone(asgi_span.data["http"]["error"])
        self.assertIsNone(asgi_span.data["http"]["params"])

    def test_secret_scrubbing(self):
        result = None
        with async_tracer.start_active_span("test"):
            result = requests.get(testenv["fastapi_server"] + "/?secret=shhh")

        self.assertEqual(result.status_code, 200)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span.data["http"]["path"], "/")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 200)

        self.assertIsNone(asgi_span.data["http"]["error"])
        self.assertEqual(asgi_span.data["http"]["params"], "secret=<redacted>")

    def test_synthetic_request(self):
        request_headers = {"X-INSTANA-SYNTHETIC": "1"}
        with async_tracer.start_active_span("test"):
            result = requests.get(
                testenv["fastapi_server"] + "/", headers=request_headers
            )

        self.assertEqual(result.status_code, 200)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span.data["http"]["path"], "/")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 200)

        self.assertIsNone(asgi_span.data["http"]["error"])
        self.assertIsNone(asgi_span.data["http"]["params"])

        self.assertTrue(asgi_span.sy)
        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

    def test_request_header_capture(self):
        from instana.singletons import agent

        # The background FastAPI server is pre-configured with custom headers to capture

        request_headers = {"X-Capture-This": "this", "X-Capture-That": "that"}

        with async_tracer.start_active_span("test"):
            result = requests.get(
                testenv["fastapi_server"] + "/", headers=request_headers
            )

        self.assertEqual(result.status_code, 200)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span.data["http"]["path"], "/")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 200)

        self.assertIsNone(asgi_span.data["http"]["error"])
        self.assertIsNone(asgi_span.data["http"]["params"])

        self.assertIn("X-Capture-This", asgi_span.data["http"]["header"])
        self.assertEqual("this", asgi_span.data["http"]["header"]["X-Capture-This"])
        self.assertIn("X-Capture-That", asgi_span.data["http"]["header"])
        self.assertEqual("that", asgi_span.data["http"]["header"]["X-Capture-That"])

    def test_response_header_capture(self):
        from instana.singletons import agent

        # The background FastAPI server is pre-configured with custom headers to capture

        with async_tracer.start_active_span("test"):
            result = requests.get(testenv["fastapi_server"] + "/response_headers")

        self.assertEqual(result.status_code, 200)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(len(spans), 3)

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
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

    def test_non_async_simple(self):
        with async_tracer.start_active_span("test"):
            result = requests.get(testenv["fastapi_server"] + "/non_async_simple")

        self.assertEqual(result.status_code, 200)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(5, len(spans))

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = (
            lambda span: span.n == "urllib3" and span.p == test_span.s
        )
        urllib3_span1 = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span1)

        span_filter = (
            lambda span: span.n == "asgi" and span.p == urllib3_span1.s
        )
        asgi_span1 = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span1)

        span_filter = (
            lambda span: span.n == "urllib3" and span.p == asgi_span1.s
        )
        urllib3_span2 = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span2)

        span_filter = (
            lambda span: span.n == "asgi" and span.p == urllib3_span2.s
        )
        asgi_span2 = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span2)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, urllib3_span1.t)
        self.assertEqual(traceId, asgi_span1.t)
        self.assertEqual(traceId, urllib3_span2.t)
        self.assertEqual(traceId, asgi_span2.t)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span1.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span1.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span1.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span1.ec)
        self.assertEqual(asgi_span1.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span1.data["http"]["path"], "/non_async_simple")
        self.assertEqual(asgi_span1.data["http"]["path_tpl"], "/non_async_simple")
        self.assertEqual(asgi_span1.data["http"]["method"], "GET")
        self.assertEqual(asgi_span1.data["http"]["status"], 200)

        self.assertIsNone(asgi_span1.data["http"]["error"])
        self.assertIsNone(asgi_span1.data["http"]["params"])

    def test_non_async_threadpool(self):
        with async_tracer.start_active_span("test"):
            result = requests.get(testenv["fastapi_server"] + "/non_async_threadpool")

        self.assertEqual(result.status_code, 200)

        spans = async_tracer.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(test_span)

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(urllib3_span)

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        self.assertTrue(asgi_span)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)
        self.assertEqual(urllib3_span.t, asgi_span.t)

        # Parent relationships
        self.assertEqual(asgi_span.p, urllib3_span.s)
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIn("X-INSTANA-T", result.headers)
        self.assertEqual(result.headers["X-INSTANA-T"], asgi_span.t)

        self.assertIn("X-INSTANA-S", result.headers)
        self.assertEqual(result.headers["X-INSTANA-S"], asgi_span.s)

        self.assertIn("X-INSTANA-L", result.headers)
        self.assertEqual(result.headers["X-INSTANA-L"], "1")

        self.assertIn("Server-Timing", result.headers)
        server_timing_value = "intid;desc=%s" % asgi_span.t
        self.assertEqual(result.headers["Server-Timing"], server_timing_value)

        self.assertIsNone(asgi_span.ec)
        self.assertEqual(asgi_span.data["http"]["host"], "127.0.0.1")
        self.assertEqual(asgi_span.data["http"]["path"], "/non_async_threadpool")
        self.assertEqual(asgi_span.data["http"]["path_tpl"], "/non_async_threadpool")
        self.assertEqual(asgi_span.data["http"]["method"], "GET")
        self.assertEqual(asgi_span.data["http"]["status"], 200)

        self.assertIsNone(asgi_span.data["http"]["error"])
        self.assertIsNone(asgi_span.data["http"]["params"])
