# (c) Copyright IBM Corp. 2026

import threading
import time
from typing import Generator, Optional
from urllib.parse import urlencode

import pytest
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

import tests.apps.twisted_server  # noqa: F401
from instana.singletons import agent, get_tracer
from instana.span.span import get_current_span
from tests.helpers import get_first_span_by_name, testenv


class TestTwistedClient:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run and restore agent options after."""
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        original_extra_http_headers = agent.options.extra_http_headers
        yield
        agent.options.extra_http_headers = original_extra_http_headers

    def _make_request(
        self,
        path: str,
        method: str = "GET",
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> tuple[object, object]:
        """Run a Twisted Agent request from within a test span."""
        result_holder = {}
        error_holder = {}

        def run_in_reactor() -> object:
            def on_response(response: object) -> None:
                result_holder["response"] = response

            def on_error(failure: object) -> None:
                error_holder["failure"] = failure

            twisted_headers = Headers({})
            if headers:
                for k, v in headers.items():
                    twisted_headers.setRawHeaders(k, [v])

            agent_obj = Agent(reactor)

            url = (testenv["twisted_server"] + path).encode("utf-8")
            if params:
                url = (
                    testenv["twisted_server"] + path + "?" + urlencode(params)
                ).encode("utf-8")

            d = agent_obj.request(method.encode("utf-8"), url, twisted_headers, None)
            d.addCallbacks(on_response, on_error)
            return d

        event = threading.Event()

        def run() -> None:
            with self.tracer.start_as_current_span("test"):
                d = run_in_reactor()

                def done(result: object) -> object:
                    event.set()
                    return result

                d.addBoth(done)

        reactor.callFromThread(run)
        event.wait(timeout=5)

        return result_holder.get("response"), error_holder.get("failure")

    @pytest.mark.parametrize(
        "path, method, status",
        [
            ("/", "GET", 200),
            ("/", "POST", 200),
            ("/301", "GET", 301),
            ("/404", "GET", 404),
        ],
    )
    def test_basic_request(self, path: str, method: str, status: int) -> None:
        response, failure = self._make_request(path, method=method)

        assert failure is None
        assert response is not None
        assert response.code == status

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "twisted-server")
        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        # Same traceId across all spans
        traceId = test_span.t
        assert client_span.t == traceId
        assert server_span.t == traceId

        # Parent relationships: test → client → server
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # No errors on any span
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # Client span attributes
        assert client_span.data["http"]["status"] == status
        assert client_span.data["http"]["method"] == method
        assert client_span.data["http"]["url"] == testenv["twisted_server"] + path

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

        # Same traceId across all spans
        traceId = test_span.t
        assert client_span.t == traceId
        assert server_span.t == traceId

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error counters
        assert not test_span.ec
        assert client_span.ec == 1
        assert server_span.ec == 1

        # Client span attributes
        assert client_span.data["http"]["status"] == 500
        assert client_span.data["http"]["method"] == "GET"
        assert client_span.data["http"]["url"] == testenv["twisted_server"] + "/500"
        assert client_span.data["http"]["error"] == "Internal Server Error"

    def test_get_with_params_to_scrub(self) -> None:
        response, failure = self._make_request("/", params={"secret": "yeah"})

        assert failure is None
        assert response is not None

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        client_span = get_first_span_by_name(spans, "twisted-client")
        test_span = get_first_span_by_name(spans, "sdk")

        # Same traceId
        assert client_span.t == test_span.t

        # Client span attributes — secret query param must be scrubbed
        assert client_span.data["http"]["status"] == 200
        assert client_span.data["http"]["method"] == "GET"
        assert client_span.data["http"]["url"] == testenv["twisted_server"] + "/"
        assert client_span.data["http"]["params"] == "secret=<redacted>"

    def test_request_header_capture(self) -> None:
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        response, failure = self._make_request(
            "/",
            headers={"X-Capture-This": "this", "X-Capture-That": "that"},
        )

        assert failure is None
        assert response is not None

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "twisted-client")

        # Outgoing request headers must be captured on the client span
        assert "X-Capture-This" in client_span.data["http"]["header"]
        assert client_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert "X-Capture-That" in client_span.data["http"]["header"]
        assert client_span.data["http"]["header"]["X-Capture-That"] == "that"

    def test_response_header_capture(self) -> None:
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        response, failure = self._make_request("/response_headers")

        assert failure is None
        assert response is not None

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "twisted-client")

        # Response headers received from server must be captured on the client span
        assert "X-Capture-This-Too" in client_span.data["http"]["header"]
        assert client_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in client_span.data["http"]["header"]
        assert client_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

    def test_agent_request_without_active_span(self) -> None:
        """Agent.request with no active span must skip client instrumentation
        (exercises the early-return branch in request_with_instana)."""
        result_holder = {}
        event = threading.Event()

        def do_request() -> None:
            # No active span — parent_span.is_recording() will be False
            agent_obj = Agent(reactor)
            d = agent_obj.request(
                b"GET",
                (testenv["twisted_server"] + "/").encode(),
                Headers({}),
                None,
            )

            def on_response(response: object) -> None:
                result_holder["code"] = response.code
                event.set()

            def on_error(failure: object) -> None:
                result_holder["error"] = str(failure)
                event.set()

            d.addCallbacks(on_response, on_error)

        reactor.callFromThread(do_request)
        event.wait(timeout=5)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        # No twisted-client span should be created (no active parent span)
        assert get_first_span_by_name(spans, "twisted-client") is None
        assert result_holder.get("code") == 200

    def test_agent_request_network_failure(self) -> None:
        """Agent.request to an unreachable host exercises the Failure errback
        path in finish_tracing (client.py)."""
        event = threading.Event()

        def do_request() -> None:
            with self.tracer.start_as_current_span("test"):
                agent_obj = Agent(reactor)
                # Port 19999 is not listening — connection refused → Failure
                d = agent_obj.request(
                    b"GET",
                    b"http://127.0.0.1:19999/",
                    Headers({}),
                    None,
                )

                def done(_: object) -> None:
                    event.set()

                d.addBoth(done)

        reactor.callFromThread(do_request)
        event.wait(timeout=5)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        twisted_client_span = get_first_span_by_name(spans, "twisted-client")

        # Failure path must mark the span errored exactly once
        assert twisted_client_span.ec == 1
        assert not get_current_span().is_recording()
