# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import time
import requests
import multiprocessing
import pytest
from typing import Generator

from instana.singletons import tracer
from tests.helpers import testenv
from tests.helpers import get_first_span_by_filter
from tests.test_utils import _TraceContextMixin


class TestSanic(_TraceContextMixin):
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup and Teardown"""
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        from tests.apps.sanic_app import launch_sanic

        self.proc = multiprocessing.Process(target=launch_sanic, args=(), daemon=True)
        self.proc.start()
        time.sleep(2)
        yield
        # Kill server after tests
        self.proc.kill()

    def test_vanilla_get(self) -> None:
        result = requests.get(testenv["sanic_server"] + "/")

        assert result.status_code == 200
        assert "X-INSTANA-T" in result.headers
        assert "X-INSTANA-S" in result.headers
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        assert spans[0].n == "asgi"

    def test_basic_get(self) -> None:
        with tracer.start_as_current_span("test"):
            result = requests.get(testenv["sanic_server"] + "/")

        assert result.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_404(self) -> None:
        with tracer.start_as_current_span("test"):
            result = requests.get(testenv["sanic_server"] + "/foo/not_an_int")

        assert result.status_code == 404

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/foo/not_an_int"
        assert not asgi_span.data["http"]["path_tpl"]
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 404
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_sanic_exception(self) -> None:
        with tracer.start_as_current_span("test"):
            result = requests.get(testenv["sanic_server"] + "/wrong")

        assert result.status_code == 400

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/wrong"
        assert asgi_span.data["http"]["path_tpl"] == "/wrong"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 400
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_500_instana_exception(self) -> None:
        with tracer.start_as_current_span("test"):
            result = requests.get(testenv["sanic_server"] + "/instana_exception")

        assert result.status_code == 500

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert asgi_span.ec == 1
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/instana_exception"
        assert asgi_span.data["http"]["path_tpl"] == "/instana_exception"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 500
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_500(self) -> None:
        with tracer.start_as_current_span("test"):
            result = requests.get(testenv["sanic_server"] + "/test_request_args")

        assert result.status_code == 500

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert asgi_span.ec == 1
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/test_request_args"
        assert asgi_span.data["http"]["path_tpl"] == "/test_request_args"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 500
        assert asgi_span.data["http"]["error"] == "Something went wrong."
        assert not asgi_span.data["http"]["params"]

    def test_path_templates(self) -> None:
        with tracer.start_as_current_span("test"):
            result = requests.get(testenv["sanic_server"] + "/foo/1")

        assert result.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/foo/1"
        assert asgi_span.data["http"]["path_tpl"] == "/foo/<foo_id:int>"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_secret_scrubbing(self) -> None:
        with tracer.start_as_current_span("test"):
            result = requests.get(testenv["sanic_server"] + "/?secret=shhh")

        assert result.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert asgi_span.data["http"]["params"] == "secret=<redacted>"

    def test_synthetic_request(self) -> None:
        request_headers = {"X-INSTANA-SYNTHETIC": "1"}
        with tracer.start_as_current_span("test"):
            result = requests.get(
                testenv["sanic_server"] + "/", headers=request_headers
            )

        assert result.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert asgi_span.sy
        assert not urllib3_span.sy
        assert not test_span.sy

    def test_request_header_capture(self) -> None:
        request_headers = {"X-Capture-This": "this", "X-Capture-That": "that"}
        with tracer.start_as_current_span("test"):
            result = requests.get(
                testenv["sanic_server"] + "/", headers=request_headers
            )

        assert result.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/"
        assert asgi_span.data["http"]["path_tpl"] == "/"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert "X-Capture-This" in asgi_span.data["http"]["header"]
        assert "this" == asgi_span.data["http"]["header"]["X-Capture-This"]
        assert "X-Capture-That" in asgi_span.data["http"]["header"]
        assert "that" == asgi_span.data["http"]["header"]["X-Capture-That"]

    def test_response_header_capture(self) -> None:
        with tracer.start_as_current_span("test"):
            result = requests.get(testenv["sanic_server"] + "/response_headers")

        assert result.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        span_filter = (
            lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        )
        test_span = get_first_span_by_filter(spans, span_filter)
        assert test_span

        span_filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, span_filter)
        assert urllib3_span

        span_filter = lambda span: span.n == "asgi"
        asgi_span = get_first_span_by_filter(spans, span_filter)
        assert asgi_span

        self.assertTraceContextPropagated(test_span, urllib3_span)
        self.assertTraceContextPropagated(urllib3_span, asgi_span)

        assert "X-INSTANA-T" in result.headers
        assert result.headers["X-INSTANA-T"] == str(asgi_span.t)
        assert "X-INSTANA-S" in result.headers
        assert result.headers["X-INSTANA-S"] == str(asgi_span.s)
        assert "X-INSTANA-L" in result.headers
        assert result.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in result.headers
        assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == "127.0.0.1:1337"
        assert asgi_span.data["http"]["path"] == "/response_headers"
        assert asgi_span.data["http"]["path_tpl"] == "/response_headers"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200

        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert "X-Capture-This-Too" in asgi_span.data["http"]["header"]
        assert "this too" == asgi_span.data["http"]["header"]["X-Capture-This-Too"]
        assert "X-Capture-That-Too" in asgi_span.data["http"]["header"]
        assert "that too" == asgi_span.data["http"]["header"]["X-Capture-That-Too"]
