# (c) Copyright IBM Corp. 2026

import time
from typing import Generator

import pytest
import requests

import tests.apps.twisted_server  # noqa: F401
from instana.singletons import agent, get_tracer
from instana.util.ids import hex_id
from tests.helpers import get_first_span_by_name, testenv


class TestTwistedServer:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run and restore agent options after."""
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        original_extra_http_headers = agent.options.extra_http_headers
        yield
        agent.options.extra_http_headers = original_extra_http_headers

    def test_get(self) -> None:
        with self.tracer.start_as_current_span("test"):
            response = requests.get(testenv["twisted_server"] + "/")

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        twisted_span = get_first_span_by_name(spans, "twisted-server")
        urllib3_span = get_first_span_by_name(spans, "urllib3")
        test_span = get_first_span_by_name(spans, "sdk")

        # Same traceId across all spans
        traceId = test_span.t
        assert urllib3_span.t == traceId
        assert twisted_span.t == traceId

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert twisted_span.p == urllib3_span.s

        # No errors on any span
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not twisted_span.ec

        # Server span attributes
        assert twisted_span.data["http"]["status"] == 200
        assert twisted_span.data["http"]["url"] == testenv["twisted_server"] + "/"
        assert not twisted_span.data["http"].get("params")
        assert twisted_span.data["http"]["method"] == "GET"
        assert not twisted_span.stack

        # Synthetic flag
        assert not twisted_span.sy
        assert not urllib3_span.sy
        assert not test_span.sy

        # Correlation headers injected into response
        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(twisted_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_post(self) -> None:
        with self.tracer.start_as_current_span("test"):
            response = requests.post(
                testenv["twisted_server"] + "/", data={"hello": "post"}
            )

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        twisted_span = get_first_span_by_name(spans, "twisted-server")
        urllib3_span = get_first_span_by_name(spans, "urllib3")
        test_span = get_first_span_by_name(spans, "sdk")

        # Same traceId across all spans
        traceId = test_span.t
        assert urllib3_span.t == traceId
        assert twisted_span.t == traceId

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert twisted_span.p == urllib3_span.s

        # No errors on any span
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not twisted_span.ec

        # Server span attributes
        assert twisted_span.data["http"]["status"] == 200
        assert twisted_span.data["http"]["url"] == testenv["twisted_server"] + "/"
        assert not twisted_span.data["http"].get("params")
        assert twisted_span.data["http"]["method"] == "POST"
        assert not twisted_span.stack

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(twisted_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_synthetic_request(self) -> None:
        with self.tracer.start_as_current_span("test"):
            _ = requests.get(
                testenv["twisted_server"] + "/",
                headers={"X-INSTANA-SYNTHETIC": "1"},
            )

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        twisted_span = get_first_span_by_name(spans, "twisted-server")
        urllib3_span = get_first_span_by_name(spans, "urllib3")
        test_span = get_first_span_by_name(spans, "sdk")

        assert twisted_span.sy
        assert not urllib3_span.sy
        assert not test_span.sy

    def test_get_301(self) -> None:
        with self.tracer.start_as_current_span("test"):
            # Don't follow redirects so we capture the 301 span
            _ = requests.get(
                testenv["twisted_server"] + "/301",
                allow_redirects=False,
            )

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        twisted_span = get_first_span_by_name(spans, "twisted-server")
        urllib3_span = get_first_span_by_name(spans, "urllib3")
        test_span = get_first_span_by_name(spans, "sdk")

        # Same traceId across all spans
        traceId = test_span.t
        assert urllib3_span.t == traceId
        assert twisted_span.t == traceId

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert twisted_span.p == urllib3_span.s

        # No errors on any span
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not twisted_span.ec

        # Server span attributes
        assert twisted_span.data["http"]["status"] == 301
        assert twisted_span.data["http"]["url"] == testenv["twisted_server"] + "/301"
        assert not twisted_span.data["http"].get("params")
        assert twisted_span.data["http"]["method"] == "GET"
        assert not twisted_span.stack

    def test_get_404(self) -> None:
        with self.tracer.start_as_current_span("test"):
            _ = requests.get(testenv["twisted_server"] + "/404")

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        twisted_span = get_first_span_by_name(spans, "twisted-server")
        urllib3_span = get_first_span_by_name(spans, "urllib3")
        test_span = get_first_span_by_name(spans, "sdk")

        # Same traceId across all spans
        traceId = test_span.t
        assert urllib3_span.t == traceId
        assert twisted_span.t == traceId

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert twisted_span.p == urllib3_span.s

        # 404 is a client error — no span should be marked errored
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not twisted_span.ec

        # Server span attributes
        assert twisted_span.data["http"]["status"] == 404
        assert twisted_span.data["http"]["url"] == testenv["twisted_server"] + "/404"
        assert twisted_span.data["http"]["method"] == "GET"
        assert not twisted_span.stack

    def test_get_500(self) -> None:
        with self.tracer.start_as_current_span("test"):
            _ = requests.get(testenv["twisted_server"] + "/500")

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        twisted_span = get_first_span_by_name(spans, "twisted-server")
        urllib3_span = get_first_span_by_name(spans, "urllib3")
        test_span = get_first_span_by_name(spans, "sdk")

        # Same traceId across all spans
        traceId = test_span.t
        assert urllib3_span.t == traceId
        assert twisted_span.t == traceId

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert twisted_span.p == urllib3_span.s

        # 500 must mark both server and upstream urllib3 span as errored
        assert not test_span.ec
        assert urllib3_span.ec == 1
        assert twisted_span.ec == 1

        # Server span attributes
        assert twisted_span.data["http"]["status"] == 500
        assert twisted_span.data["http"]["url"] == testenv["twisted_server"] + "/500"
        assert twisted_span.data["http"]["method"] == "GET"
        assert not twisted_span.stack
        assert twisted_span.data["http"]["error"] == "Internal Server Error"

    def test_get_with_params_to_scrub(self) -> None:
        with self.tracer.start_as_current_span("test"):
            _ = requests.get(
                testenv["twisted_server"] + "/",
                params={"secret": "yeah"},
            )

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        twisted_span = get_first_span_by_name(spans, "twisted-server")
        test_span = get_first_span_by_name(spans, "sdk")

        # Same traceId
        assert twisted_span.t == test_span.t

        # Server span attributes — secret query param must be scrubbed
        assert twisted_span.data["http"]["status"] == 200
        assert twisted_span.data["http"]["url"] == testenv["twisted_server"] + "/"
        assert twisted_span.data["http"]["params"] == "secret=<redacted>"
        assert twisted_span.data["http"]["method"] == "GET"
        assert not twisted_span.stack

    def test_request_header_capture(self) -> None:
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        with self.tracer.start_as_current_span("test"):
            _ = requests.get(
                testenv["twisted_server"] + "/",
                params={"secret": "iloveyou"},
                headers={"X-Capture-This": "this", "X-Capture-That": "that"},
            )

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        twisted_span = get_first_span_by_name(spans, "twisted-server")

        # Incoming request headers must be captured on the server span
        assert "X-Capture-This" in twisted_span.data["http"]["header"]
        assert twisted_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert "X-Capture-That" in twisted_span.data["http"]["header"]
        assert twisted_span.data["http"]["header"]["X-Capture-That"] == "that"

    def test_response_header_capture(self) -> None:
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        with self.tracer.start_as_current_span("test"):
            _ = requests.get(
                testenv["twisted_server"] + "/response_headers",
                params={"secret": "itsasecret"},
            )

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        twisted_span = get_first_span_by_name(spans, "twisted-server")

        # Response headers set by the handler must be captured on the server span
        assert "X-Capture-This-Too" in twisted_span.data["http"]["header"]
        assert twisted_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in twisted_span.data["http"]["header"]
        assert twisted_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

    def test_no_tracing_context(self) -> None:
        """Requests without an active parent span still produce a root twisted-server span."""
        # No start_as_current_span wrapper — simulates an uninstrumented caller
        response = requests.get(testenv["twisted_server"] + "/")

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) >= 1

        twisted_span = get_first_span_by_name(spans, "twisted-server")

        # Server span attributes
        assert twisted_span.data["http"]["status"] == 200
        # No parent — this is a root span
        assert not twisted_span.p

        # Correlation headers still injected even without a parent
        assert "X-INSTANA-T" in response.headers
        assert "X-INSTANA-S" in response.headers
        assert "Server-Timing" in response.headers

    def test_fetch_propagates_span(self) -> None:
        """GET /fetch?url=... triggers an outbound Agent.request inside the Twisted
        reactor.  Because the server span is attached to the contextvars via
        context.attach(), the twisted-client instrumentation finds it as the
        current span and produces a full 5-span trace chain:
        sdk → urllib3 → twisted-server (/fetch) → twisted-client → twisted-server (/)
        """
        with self.tracer.start_as_current_span("test"):
            response = requests.get(
                testenv["twisted_server"] + "/fetch",
                params={"url": testenv["twisted_server"] + "/"},
            )

        time.sleep(0.5)
        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        # sdk + urllib3 (outer) + twisted-server (fetch handler)
        # + twisted-client (outbound) + twisted-server (root /)
        assert len(spans) == 5

        test_span = get_first_span_by_name(spans, "sdk")
        urllib3_span = get_first_span_by_name(spans, "urllib3")
        client_span = get_first_span_by_name(spans, "twisted-client")

        server_spans = [s for s in spans if s.n == "twisted-server"]
        assert len(server_spans) == 2
        fetch_server_span = next(
            s for s in server_spans if "/fetch" in s.data["http"]["url"]
        )
        root_server_span = next(
            s for s in server_spans if "/fetch" not in s.data["http"]["url"]
        )

        # All spans share the same traceId
        traceId = test_span.t
        assert urllib3_span.t == traceId
        assert fetch_server_span.t == traceId
        assert client_span.t == traceId
        assert root_server_span.t == traceId

        # Full parent chain: sdk → urllib3 → fetch-server → client → root-server
        assert urllib3_span.p == test_span.s
        assert fetch_server_span.p == urllib3_span.s
        assert client_span.p == fetch_server_span.s
        assert root_server_span.p == client_span.s

        # No errors on any span
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not fetch_server_span.ec
        assert not client_span.ec
        assert not root_server_span.ec

        # Span-under-test attributes
        assert fetch_server_span.data["http"]["status"] == 200
        assert fetch_server_span.data["http"]["method"] == "GET"
        assert client_span.data["http"]["status"] == 200
        assert root_server_span.data["http"]["status"] == 200
