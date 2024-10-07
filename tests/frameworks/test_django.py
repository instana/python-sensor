# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os

import urllib3
import pytest
from typing import Generator
from django.apps import apps
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from instana.util.ids import hex_id
from tests.apps.app_django import INSTALLED_APPS
from instana.singletons import agent, tracer
from tests.helpers import (
    fail_with_message_and_span_dump,
    get_first_span_by_filter,
    drop_log_spans_from_list,
)
from instana.instrumentation.django.middleware import url_pattern_route

apps.populate(INSTALLED_APPS)


class TestDjango(StaticLiveServerTestCase):
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup and Teardown"""
        self.http = urllib3.PoolManager()
        self.recorder = tracer.span_processor
        # clear all spans before a test run
        self.recorder.clear_spans()
        yield
        # clear the INSTANA_DISABLE_W3C_TRACE_CORRELATION environment variable
        os.environ["INSTANA_DISABLE_W3C_TRACE_CORRELATION"] = ""

    def test_basic_request(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", self.live_server_url + "/", fields={"test": 1}
            )

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 3 == len(spans)

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(django_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(django_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(django_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert "django" == django_span.n

        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == django_span.t

        assert urllib3_span.p == test_span.s
        assert django_span.p == urllib3_span.s

        assert django_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        assert django_span.ec is None
        assert "/" == django_span.data["http"]["url"]
        assert "GET" == django_span.data["http"]["method"]
        assert 200 == django_span.data["http"]["status"]
        assert "test=1" == django_span.data["http"]["params"]
        assert "^$" == django_span.data["http"]["path_tpl"]

        assert django_span.stack is None

    def test_synthetic_request(self) -> None:
        headers = {"X-INSTANA-SYNTHETIC": "1"}

        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", self.live_server_url + "/", headers=headers
            )

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 3 == len(spans)

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        assert "^$" == django_span.data["http"]["path_tpl"]

        assert django_span.sy
        assert urllib3_span.sy is None
        assert test_span.sy is None

    def test_request_with_error(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", self.live_server_url + "/cause_error")

        assert response
        assert 500 == response.status

        spans = self.recorder.queued_spans()
        spans = drop_log_spans_from_list(spans)

        span_count = len(spans)
        if span_count != 3:
            msg = "Expected 3 spans but got %d" % span_count
            fail_with_message_and_span_dump(msg, spans)

        filter = lambda span: span.n == "sdk" and span.data["sdk"]["name"] == "test"
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "urllib3"
        urllib3_span = get_first_span_by_filter(spans, filter)
        assert urllib3_span

        filter = lambda span: span.n == "django"
        django_span = get_first_span_by_filter(spans, filter)
        assert django_span

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(django_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(django_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(django_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert "django" == django_span.n

        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == django_span.t

        assert urllib3_span.p == test_span.s
        assert django_span.p == urllib3_span.s

        assert 1 == django_span.ec

        assert "/cause_error" == django_span.data["http"]["url"]
        assert "GET" == django_span.data["http"]["method"]
        assert 500 == django_span.data["http"]["status"]
        assert "This is a fake error: /cause-error" == django_span.data["http"]["error"]
        assert "^cause_error$" == django_span.data["http"]["path_tpl"]
        assert django_span.stack is None

    def test_request_with_not_found(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", self.live_server_url + "/not_found")

        assert response
        assert 404 == response.status

        spans = self.recorder.queued_spans()
        spans = drop_log_spans_from_list(spans)

        span_count = len(spans)
        if span_count != 3:
            msg = "Expected 3 spans but got %d" % span_count
            fail_with_message_and_span_dump(msg, spans)

        filter = lambda span: span.n == "django"
        django_span = get_first_span_by_filter(spans, filter)
        assert django_span

        assert django_span.ec is None
        assert 404 == django_span.data["http"]["status"]

    def test_request_with_not_found_no_route(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", self.live_server_url + "/no_route")

        assert response
        assert 404 == response.status

        spans = self.recorder.queued_spans()
        spans = drop_log_spans_from_list(spans)

        span_count = len(spans)
        if span_count != 3:
            msg = "Expected 3 spans but got %d" % span_count
            fail_with_message_and_span_dump(msg, spans)

        filter = lambda span: span.n == "django"
        django_span = get_first_span_by_filter(spans, filter)
        assert django_span
        assert django_span.data["http"]["path_tpl"] is None
        assert django_span.ec is None
        assert 404 == django_span.data["http"]["status"]

    def test_complex_request(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", self.live_server_url + "/complex")

        assert response
        assert 200 == response.status
        spans = self.recorder.queued_spans()
        assert 5 == len(spans)

        test_span = spans[4]
        urllib3_span = spans[3]
        django_span = spans[2]
        otel_span1 = spans[1]
        otel_span2 = spans[0]

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(django_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(django_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(django_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert "django" == django_span.n
        assert "sdk" == otel_span1.n
        assert "sdk" == otel_span2.n

        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == django_span.t
        assert django_span.t == otel_span1.t
        assert otel_span1.t == otel_span2.t

        assert urllib3_span.p == test_span.s
        assert django_span.p == urllib3_span.s
        assert otel_span1.p == django_span.s
        assert otel_span2.p == otel_span1.s

        assert django_span.ec is None
        assert django_span.stack is None

        assert otel_span1.data["sdk"]["type"] == "exit"
        assert otel_span2.data["sdk"]["type"] == otel_span1.data["sdk"]["type"]
        otel_span1.data["sdk"]["name"] == "asteroid"
        otel_span2.data["sdk"]["name"] == "spacedust"

        assert "/complex" == django_span.data["http"]["url"]
        assert "GET" == django_span.data["http"]["method"]
        assert 200 == django_span.data["http"]["status"]
        assert "^complex$" == django_span.data["http"]["path_tpl"]

    def test_request_header_capture(self) -> None:
        # Hack together a manual custom headers list
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        request_headers = {"X-Capture-This": "this", "X-Capture-That": "that"}

        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", self.live_server_url + "/", headers=request_headers
            )
            # response = self.client.get('/')

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 3 == len(spans)

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert "django" == django_span.n

        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == django_span.t

        assert urllib3_span.p == test_span.s
        assert django_span.p == urllib3_span.s

        assert django_span.ec is None
        assert django_span.stack is None

        assert "/" == django_span.data["http"]["url"]
        assert "GET" == django_span.data["http"]["method"]
        assert 200 == django_span.data["http"]["status"]
        assert "^$" == django_span.data["http"]["path_tpl"]

        assert "X-Capture-This" in django_span.data["http"]["header"]
        assert "this" == django_span.data["http"]["header"]["X-Capture-This"]
        assert "X-Capture-That" in django_span.data["http"]["header"]
        assert "that" == django_span.data["http"]["header"]["X-Capture-That"]

        agent.options.extra_http_headers = original_extra_http_headers

    def test_response_header_capture(self) -> None:
        # Hack together a manual custom headers list
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", self.live_server_url + "/response_with_headers"
            )

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 3 == len(spans)

        test_span = spans[2]
        urllib3_span = spans[1]
        django_span = spans[0]

        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert "django" == django_span.n

        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == django_span.t

        assert urllib3_span.p == test_span.s
        assert django_span.p == urllib3_span.s

        assert django_span.ec is None
        assert django_span.stack is None

        assert "/response_with_headers" == django_span.data["http"]["url"]
        assert "GET" == django_span.data["http"]["method"]
        assert 200 == django_span.data["http"]["status"]
        assert "^response_with_headers$" == django_span.data["http"]["path_tpl"]

        assert "X-Capture-This-Too" in django_span.data["http"]["header"]
        assert "this too" == django_span.data["http"]["header"]["X-Capture-This-Too"]
        assert "X-Capture-That-Too" in django_span.data["http"]["header"]
        assert "that too" == django_span.data["http"]["header"]["X-Capture-That-Too"]

        agent.options.extra_http_headers = original_extra_http_headers

    @pytest.mark.skip("Handled when type of trace and span ids are modified to str")
    def test_with_incoming_context(self) -> None:
        request_headers = dict()
        request_headers["X-INSTANA-T"] = "1"
        request_headers["X-INSTANA-S"] = "1"
        request_headers["traceparent"] = (
            "01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01-788777"
        )
        request_headers["tracestate"] = (
            "rojo=00f067aa0ba902b7,in=a3ce929d0e0e4736;8357ccd9da194656,congo=t61rcWkgMzE"
        )

        response = self.http.request(
            "GET", self.live_server_url + "/", headers=request_headers
        )

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 1 == len(spans)

        django_span = spans[0]

        # assert django_span.t == '0000000000000001'
        # assert django_span.p == '0000000000000001'
        assert django_span.t == 1
        assert django_span.p == 1

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(django_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(django_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(django_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert "traceparent" in response.headers
        # The incoming traceparent header had version 01 (which does not exist at the time of writing), but since we
        # support version 00, we also need to pass down 00 for the version field.
        assert (
            "00-4bf92f3577b34da6a3ce929d0e0e4736-{}-01".format(django_span.s)
            == response.headers["traceparent"]
        )

        assert "tracestate" in response.headers
        assert (
            "in={};{},rojo=00f067aa0ba902b7,congo=t61rcWkgMzE".format(
                django_span.t, django_span.s
            )
            == response.headers["tracestate"]
        )

    @pytest.mark.skip("Handled when type of trace and span ids are modified to str")
    def test_with_incoming_context_and_correlation(self) -> None:
        request_headers = dict()
        request_headers["X-INSTANA-T"] = "1"
        request_headers["X-INSTANA-S"] = "1"
        request_headers["X-INSTANA-L"] = (
            "1, correlationType=web; correlationId=1234567890abcdef"
        )
        request_headers["traceparent"] = (
            "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        )
        request_headers["tracestate"] = (
            "rojo=00f067aa0ba902b7,in=a3ce929d0e0e4736;8357ccd9da194656,congo=t61rcWkgMzE"
        )

        response = self.http.request(
            "GET", self.live_server_url + "/", headers=request_headers
        )

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 1 == len(spans)

        django_span = spans[0]

        assert django_span.t == "a3ce929d0e0e4736"
        assert django_span.p == "00f067aa0ba902b7"
        assert django_span.ia.t == "a3ce929d0e0e4736"
        assert django_span.ia.p == "8357ccd9da194656"
        assert django_span.lt == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert django_span.tp
        assert django_span.crtp == "web"
        assert django_span.crid == "1234567890abcdef"

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(django_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(django_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(django_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert "traceparent" in response.headers
        assert (
            "00-4bf92f3577b34da6a3ce929d0e0e4736-{}-01".format(django_span.s)
            == response.headers["traceparent"]
        )

        assert "tracestate" in response.headers
        assert (
            "in={};{},rojo=00f067aa0ba902b7,congo=t61rcWkgMzE".format(
                django_span.t, django_span.s
            )
            == response.headers["tracestate"]
        )

    @pytest.mark.skip("Handled when type of trace and span ids are modified to str")
    def test_with_incoming_traceparent_tracestate(self) -> None:
        request_headers = dict()
        request_headers["traceparent"] = (
            "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        )
        request_headers["tracestate"] = (
            "rojo=00f067aa0ba902b7,in=a3ce929d0e0e4736;8357ccd9da194656,congo=t61rcWkgMzE"
        )

        response = self.http.request(
            "GET", self.live_server_url + "/", headers=request_headers
        )

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 1 == len(spans)

        django_span = spans[0]

        assert (
            django_span.t == "a3ce929d0e0e4736"
        )  # last 16 chars from traceparent trace_id
        assert django_span.p == "00f067aa0ba902b7"
        assert django_span.ia.t == "a3ce929d0e0e4736"
        assert django_span.ia.p == "8357ccd9da194656"
        assert django_span.lt == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert django_span.tp

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(django_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(django_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(django_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert "traceparent" in response.headers
        assert (
            "00-4bf92f3577b34da6a3ce929d0e0e4736-{}-01".format(django_span.s)
            == response.headers["traceparent"]
        )

        assert "tracestate" in response.headers
        assert (
            "in=a3ce929d0e0e4736;{},rojo=00f067aa0ba902b7,congo=t61rcWkgMzE".format(
                django_span.s
            )
            == response.headers["tracestate"]
        )

    @pytest.mark.skip("Handled when type of trace and span ids are modified to str")
    def test_with_incoming_traceparent_tracestate_disable_traceparent(self) -> None:
        os.environ["INSTANA_DISABLE_W3C_TRACE_CORRELATION"] = "1"
        request_headers = dict()
        request_headers["traceparent"] = (
            "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        )
        request_headers["tracestate"] = (
            "rojo=00f067aa0ba902b7,in=a3ce929d0e0e4736;8357ccd9da194656,congo=t61rcWkgMzE"
        )

        response = self.http.request(
            "GET", self.live_server_url + "/", headers=request_headers
        )

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 1 == len(spans)

        django_span = spans[0]

        assert (
            django_span.t == "a3ce929d0e0e4736"
        )  # last 16 chars from traceparent trace_id
        assert django_span.p == "8357ccd9da194656"

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(django_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(django_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(django_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert "traceparent" in response.headers
        assert (
            "00-4bf92f3577b34da6a3ce929d0e0e4736-{}-01".format(django_span.s)
            == response.headers["traceparent"]
        )

        assert "tracestate" in response.headers
        assert (
            "in={};{},rojo=00f067aa0ba902b7,congo=t61rcWkgMzE".format(
                django_span.t, django_span.s
            )
            == response.headers["tracestate"]
        )

    def test_with_incoming_mixed_case_context(self) -> None:
        request_headers = dict()
        request_headers["X-InSTANa-T"] = "0000000000000001"
        request_headers["X-instana-S"] = "0000000000000001"

        response = self.http.request(
            "GET", self.live_server_url + "/", headers=request_headers
        )

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 1 == len(spans)

        django_span = spans[0]

        # assert django_span.t == '0000000000000001'
        # assert django_span.p == '0000000000000001'
        assert django_span.t == 1
        assert django_span.p == 1

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(django_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(django_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(django_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

    def test_url_pattern_route(self) -> None:
        view_name = "app_django.another"
        path_tpl = "".join(url_pattern_route(view_name))
        assert path_tpl == "^another$"

        view_name = "app_django.complex"
        try:
            path_tpl = "".join(url_pattern_route(view_name))
        except Exception:
            path_tpl = None
        assert path_tpl is None
