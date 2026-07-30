# (c) Copyright IBM Corp. 2026

import time
import threading
from typing import Generator, Optional

import pytest
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

import tests.apps.twisted_server  # noqa: F401
from instana.singletons import agent, get_tracer
from instana.span.span import get_current_span
from instana.util.ids import hex_id
from tests.helpers import get_first_span_by_name, testenv


class TestTwistedClient:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        yield

    def _make_request(
        self,
        path: str,
        method: str = "GET",
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
    ):
        """Run a Twisted Agent request from within a test span."""
        result_holder = {}
        error_holder = {}

        def run_in_reactor():
            def on_response(response):
                result_holder["response"] = response

            def on_error(failure):
                error_holder["failure"] = failure

            twisted_headers = Headers({})
            if headers:
                for k, v in headers.items():
                    twisted_headers.setRawHeaders(k, [v])

            agent_obj = Agent(reactor)

            url = (testenv["twisted_server"] + path).encode("utf-8")
            if params:
                from urllib.parse import urlencode

                url = (
                    testenv["twisted_server"] + path + "?" + urlencode(params)
                ).encode("utf-8")

            d = agent_obj.request(method.encode("utf-8"), url, twisted_headers, None)
            d.addCallbacks(on_response, on_error)
            return d

        event = threading.Event()

        def run():
            with self.tracer.start_as_current_span("test"):
                d = run_in_reactor()

                def done(result):
                    event.set()
                    return result

                d.addBoth(done)

        reactor.callFromThread(run)
        event.wait(timeout=5)

        return result_holder.get("response"), error_holder.get("failure")

    def test_get(self) -> None:
        response, failure = self._make_request("/")

        assert failure is None
        assert response is not None
        assert response.code == 200

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships: test → client → server
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        assert server_span.data["http"]["status"] == 200
        assert testenv["twisted_server"] + "/" == server_span.data["http"]["url"]
        assert not server_span.data["http"].get("params")
        assert server_span.data["http"]["method"] == "GET"

        assert client_span.data["http"]["status"] == 200
        assert client_span.data["http"]["method"] == "GET"

        # Instana correlation headers must be present in the response
        # Twisted stores headers with canonical casing; normalise to lowercase for lookup
        response_headers = {
            k.lower(): v for k, v in response.headers.getAllRawHeaders()
        }
        assert b"x-instana-t" in response_headers
        assert response_headers[b"x-instana-t"][0].decode() == hex_id(traceId)
        assert b"x-instana-s" in response_headers
        assert response_headers[b"x-instana-s"][0].decode() == hex_id(server_span.s)
        assert b"x-instana-l" in response_headers
        assert response_headers[b"x-instana-l"][0].decode() == "1"
        assert b"server-timing" in response_headers
        assert (
            response_headers[b"server-timing"][0].decode()
            == f"intid;desc={hex_id(traceId)}"
        )

    def test_post(self) -> None:
        response, failure = self._make_request("/", method="POST")

        assert failure is None
        assert response is not None
        assert response.code == 200

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        assert server_span.data["http"]["status"] == 200
        assert testenv["twisted_server"] + "/" == server_span.data["http"]["url"]
        assert not server_span.data["http"].get("params")
        assert server_span.data["http"]["method"] == "POST"

        assert client_span.data["http"]["status"] == 200
        assert client_span.data["http"]["method"] == "POST"

    def test_get_301(self) -> None:
        response, failure = self._make_request("/301")

        assert failure is None
        assert response is not None
        assert response.code == 301

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        assert server_span.data["http"]["status"] == 301
        assert testenv["twisted_server"] + "/301" == server_span.data["http"]["url"]
        assert server_span.data["http"]["method"] == "GET"

        assert client_span.data["http"]["status"] == 301

    def test_get_404(self) -> None:
        response, failure = self._make_request("/404")

        assert failure is None
        assert response is not None
        assert response.code == 404

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        assert server_span.data["http"]["status"] == 404
        assert testenv["twisted_server"] + "/404" == server_span.data["http"]["url"]

        assert client_span.data["http"]["status"] == 404
        # 4xx marks client span as errored
        assert client_span.ec == 1

    def test_get_500(self) -> None:
        response, failure = self._make_request("/500")

        assert failure is None
        assert response is not None
        assert response.code == 500

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        assert server_span.data["http"]["status"] == 500
        assert testenv["twisted_server"] + "/500" == server_span.data["http"]["url"]

        # Error logging
        assert not test_span.ec
        assert client_span.ec == 1
        assert server_span.ec == 1

    def test_get_with_params_to_scrub(self) -> None:
        response, failure = self._make_request("/", params={"secret": "yeah"})

        assert failure is None
        assert response is not None

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        assert server_span.data["http"]["status"] == 200
        assert testenv["twisted_server"] + "/" == server_span.data["http"]["url"]
        assert server_span.data["http"]["params"] == "secret=<redacted>"

        # Client span also scrubs params
        assert client_span.data["http"]["params"] == "secret=<redacted>"
        assert client_span.data["http"]["url"].endswith("/")

    def test_request_header_capture(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        try:
            response, failure = self._make_request(
                "/",
                headers={"X-Capture-This": "this", "X-Capture-That": "that"},
            )
        finally:
            agent.options.extra_http_headers = original_extra_http_headers

        assert failure is None
        assert response is not None

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Server captures request headers
        assert "X-Capture-This" in server_span.data["http"]["header"]
        assert server_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert "X-Capture-That" in server_span.data["http"]["header"]
        assert server_span.data["http"]["header"]["X-Capture-That"] == "that"

        # Client also captures outgoing request headers
        assert "X-Capture-This" in client_span.data["http"]["header"]
        assert client_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert "X-Capture-That" in client_span.data["http"]["header"]
        assert client_span.data["http"]["header"]["X-Capture-That"] == "that"

    def test_response_header_capture(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        try:
            response, failure = self._make_request("/response_headers")
        finally:
            agent.options.extra_http_headers = original_extra_http_headers

        assert failure is None
        assert response is not None

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Server captures response headers it sets
        assert "X-Capture-This-Too" in server_span.data["http"]["header"]
        assert server_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in server_span.data["http"]["header"]
        assert server_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

        # Client captures response headers it receives
        assert "X-Capture-This-Too" in client_span.data["http"]["header"]
        assert client_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in client_span.data["http"]["header"]
        assert client_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

    def test_agent_request_without_active_span(self) -> None:
        """Agent.request with no active span must skip client instrumentation
        (exercises the early-return branch in request_with_instana)."""
        result_holder: dict = {}
        event = threading.Event()

        def do_request():
            # No active span — parent_span.is_recording() will be False
            agent_obj = Agent(reactor)
            d = agent_obj.request(
                b"GET",
                (testenv["twisted_server"] + "/").encode(),
                Headers({}),
                None,
            )

            def on_response(response):
                result_holder["code"] = response.code
                event.set()

            def on_error(failure):
                result_holder["error"] = str(failure)
                event.set()

            d.addCallbacks(on_response, on_error)

        reactor.callFromThread(do_request)
        event.wait(timeout=5)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        # No twisted-client span should be created (no active parent span)
        client_span = get_first_span_by_name(spans, "twisted-client")
        assert client_span is None
        # The server still produces its own root span
        assert result_holder.get("code") == 200

    def test_agent_request_network_failure(self) -> None:
        """Agent.request to an unreachable host exercises the Failure errback
        path in _finish_tracing (client.py:102-106)."""
        event = threading.Event()

        def do_request():
            with self.tracer.start_as_current_span("test"):
                agent_obj = Agent(reactor)
                # Port 19999 is not listening — connection refused → Failure
                d = agent_obj.request(
                    b"GET",
                    b"http://127.0.0.1:19999/",
                    Headers({}),
                    None,
                )

                def done(_):
                    event.set()

                d.addBoth(done)

        reactor.callFromThread(do_request)
        event.wait(timeout=5)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        twisted_client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert twisted_client_span
        assert test_span
        # Failure path must mark the span errored
        assert twisted_client_span.ec == 1
