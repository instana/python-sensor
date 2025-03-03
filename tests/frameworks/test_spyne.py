# (c) Copyright IBM Corp. 2025

import time
import urllib3
import pytest
from typing import Generator

from tests.apps import spyne_app
from tests.helpers import testenv
from instana.singletons import agent, tracer
from instana.span.span import get_current_span
from instana.util.ids import hex_id


class TestSpyne:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.http = urllib3.PoolManager()
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        time.sleep(0.1)

    def test_vanilla_requests(self) -> None:
        response = self.http.request("GET", testenv["spyne_server"] + "/hello")
        spans = self.recorder.queued_spans()

        assert len(spans) == 1
        assert get_current_span().is_recording() is False
        assert response.status == 200

    def test_get_request(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", testenv["spyne_server"] + "/hello")

        spans = self.recorder.queued_spans()

        assert len(spans) == 3
        assert get_current_span().is_recording() is False

        spyne_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 200 == response.status

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(spyne_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(spyne_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(spyne_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == spyne_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert spyne_span.p == urllib3_span.s

        assert spyne_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert spyne_span.ec is None

        # wsgi
        assert "spyne" == spyne_span.n
        assert (
            "127.0.0.1:" + str(testenv["spyne_port"]) == spyne_span.data["http"]["host"]
        )
        assert "/hello" == spyne_span.data["http"]["url"]
        assert "GET" == spyne_span.data["http"]["method"]
        assert 200 == spyne_span.data["http"]["status"]
        assert spyne_span.data["http"]["error"] is None
        assert spyne_span.stack is None

    def test_secret_scrubbing(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", testenv["spyne_server"] + "/say_hello?name=World&times=4&secret=sshhh")

        spans = self.recorder.queued_spans()

        assert len(spans) == 3
        assert get_current_span().is_recording() is False

        spyne_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 200 == response.status

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(spyne_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(spyne_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(spyne_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == spyne_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert spyne_span.p == urllib3_span.s

        assert spyne_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert spyne_span.ec is None

        # wsgi
        assert "spyne" == spyne_span.n
        assert (
            "127.0.0.1:" + str(testenv["spyne_port"]) == spyne_span.data["http"]["host"]
        )
        assert "/say_hello" == spyne_span.data["http"]["url"]
        assert spyne_span.data["http"]["params"] == "name=World&times=4&secret=<redacted>"
        assert "GET" == spyne_span.data["http"]["method"]
        assert 200 == spyne_span.data["http"]["status"]
        assert spyne_span.data["http"]["error"] is None
        assert spyne_span.stack is None
