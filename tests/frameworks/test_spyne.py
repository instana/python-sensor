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
        assert response.status == 200

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

        # spyne
        assert spyne_span.n == "rpc-server"
        assert spyne_span.data["rpc"]["host"] == "127.0.0.1"
        assert spyne_span.data["rpc"]["call"] == "/hello"
        assert spyne_span.data["rpc"]["port"] == str(testenv["spyne_port"])
        assert spyne_span.data["rpc"]["error"] is None
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
        assert response.status == 200

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

        # spyne
        assert spyne_span.n == "rpc-server"
        assert spyne_span.data["rpc"]["host"] == "127.0.0.1"
        assert spyne_span.data["rpc"]["call"] == "/say_hello"
        assert spyne_span.data["rpc"]["params"] == "name=World&times=4&secret=<redacted>"
        assert spyne_span.data["rpc"]["port"] == str(testenv["spyne_port"])
        assert spyne_span.data["rpc"]["error"] is None
        assert spyne_span.stack is None

    def test_custom_404(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", testenv["spyne_server"] + "/custom_404?user_id=9876")

        spans = self.recorder.queued_spans()

        assert len(spans) == 4
        assert get_current_span().is_recording() is False

        log_span = spans[0]
        spyne_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert response
        assert response.status == 404

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

        # Synthetic
        assert spyne_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert spyne_span.ec is None

        # spyne
        assert spyne_span.n == "rpc-server"
        assert spyne_span.data["rpc"]["host"] == "127.0.0.1"
        assert spyne_span.data["rpc"]["call"] == "/custom_404"
        assert spyne_span.data["rpc"]["port"] == str(testenv["spyne_port"])
        assert spyne_span.data["rpc"]["params"] == "user_id=9876"
        assert spyne_span.data["rpc"]["error"] is None
        assert spyne_span.stack is None

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 404
        assert (
            testenv["spyne_server"] + "/custom_404" == urllib3_span.data["http"]["url"]
        )
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

    def test_404(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", testenv["spyne_server"] + "/11111")

        spans = self.recorder.queued_spans()

        assert len(spans) == 3
        assert get_current_span().is_recording() is False

        spyne_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert response.status == 404

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

        # Synthetic
        assert spyne_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert spyne_span.ec is None

        # spyne
        assert spyne_span.n == "rpc-server"
        assert spyne_span.data["rpc"]["host"] == "127.0.0.1"
        assert spyne_span.data["rpc"]["call"] == "/11111"
        assert spyne_span.data["rpc"]["port"] == str(testenv["spyne_port"])
        assert spyne_span.data["rpc"]["error"] is None
        assert spyne_span.stack is None

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 404
        assert (
            testenv["spyne_server"] + "/11111" == urllib3_span.data["http"]["url"]
        )
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

    def test_500(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", testenv["spyne_server"] + "/exception")

        spans = self.recorder.queued_spans()

        assert len(spans) == 4
        assert get_current_span().is_recording() is False

        log_span = spans[0]
        spyne_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert response
        assert response.status == 500

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
        assert urllib3_span.ec == 1
        assert spyne_span.ec == 1

        # spyne
        assert spyne_span.n == "rpc-server"
        assert spyne_span.data["rpc"]["host"] == "127.0.0.1"
        assert spyne_span.data["rpc"]["call"] == "/exception"
        assert spyne_span.data["rpc"]["port"] == str(testenv["spyne_port"])        
        assert spyne_span.data["rpc"]["error"]
        assert spyne_span.stack is None
