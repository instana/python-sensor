# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import pytest
import urllib3
from typing import Generator

from instana.util.ids import hex_id
import tests.apps.pyramid.pyramid_app
from tests.helpers import testenv
from instana.singletons import tracer, agent
from instana.span.span import get_current_span


class TestPyramid:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.http = urllib3.PoolManager()
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

    def test_vanilla_requests(self) -> None:
        r = self.http.request("GET", testenv["pyramid_server"] + "/")
        assert r.status == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

    def test_get_request(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", testenv["pyramid_server"] + "/")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response.status == 200

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(pyramid_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(pyramid_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(pyramid_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert not get_current_span().is_recording()

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == pyramid_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert pyramid_span.p == urllib3_span.s

        # Synthetic
        assert not pyramid_span.sy
        assert not urllib3_span.sy
        assert not test_span.sy

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not pyramid_span.ec

        # wsgi
        assert pyramid_span.n == "wsgi"
        assert pyramid_span.data["http"]["host"] == "127.0.0.1:" + str(testenv["pyramid_port"])
        assert pyramid_span.data["http"]["url"] == "/"
        assert pyramid_span.data["http"]["method"] == "GET"
        assert pyramid_span.data["http"]["status"] == 200
        assert not pyramid_span.data["http"]["error"]
        assert pyramid_span.data["http"]["path_tpl"] == "/"

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert testenv["pyramid_server"] + "/" == urllib3_span.data["http"]["url"]
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

    def test_synthetic_request(self) -> None:
        headers = {"X-INSTANA-SYNTHETIC": "1"}

        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", testenv["pyramid_server"] + "/", headers=headers
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response.status == 200

        assert pyramid_span.sy
        assert not urllib3_span.sy
        assert not test_span.sy

    def test_500(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", testenv["pyramid_server"] + "/500")

        spans = self.recorder.queued_spans()

        assert len(spans) == 3

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response.status == 500

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(pyramid_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(pyramid_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(pyramid_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert not get_current_span().is_recording()

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == pyramid_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert pyramid_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert urllib3_span.ec == 1
        assert pyramid_span.ec == 1

        # wsgi
        assert pyramid_span.n == "wsgi"
        assert pyramid_span.data["http"]["host"] == "127.0.0.1:" + str(testenv["pyramid_port"])
        assert pyramid_span.data["http"]["url"] == "/500"
        assert pyramid_span.data["http"]["method"] == "GET"
        assert pyramid_span.data["http"]["status"] == 500
        assert pyramid_span.data["http"]["error"] == "internal error"
        assert pyramid_span.data["http"]["path_tpl"] == "/500"

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 500
        assert testenv["pyramid_server"] + "/500" == urllib3_span.data["http"]["url"]
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

    def test_exception(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", testenv["pyramid_server"] + "/exception"
            )

        spans = self.recorder.queued_spans()

        assert len(spans) == 3

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response.status == 500

        assert not get_current_span().is_recording()

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == pyramid_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert pyramid_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert urllib3_span.ec == 1
        assert pyramid_span.ec == 1

        # wsgi
        assert pyramid_span.n == "wsgi"
        assert pyramid_span.data["http"]["host"] == "127.0.0.1:" + str(testenv["pyramid_port"])
        assert pyramid_span.data["http"]["url"] == "/exception"
        assert pyramid_span.data["http"]["method"] == "GET"
        assert pyramid_span.data["http"]["status"] == 500
        assert pyramid_span.data["http"]["error"] == "fake exception"
        assert not pyramid_span.data["http"]["path_tpl"]

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 500
        assert (
            testenv["pyramid_server"] + "/exception" == urllib3_span.data["http"]["url"]
        )
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

    def test_response_header_capture(self) -> None:
        # Hack together a manual custom headers list
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", testenv["pyramid_server"] + "/response_headers"
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert response.status == 200

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == pyramid_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert pyramid_span.p == urllib3_span.s

        # Synthetic
        assert not pyramid_span.sy
        assert not urllib3_span.sy
        assert not test_span.sy

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not pyramid_span.ec

        # wsgi
        assert pyramid_span.n == "wsgi"
        assert pyramid_span.data["http"]["host"] == "127.0.0.1:" + str(testenv["pyramid_port"])
        assert pyramid_span.data["http"]["url"] == "/response_headers"
        assert pyramid_span.data["http"]["method"] == "GET"
        assert pyramid_span.data["http"]["status"] == 200
        assert not pyramid_span.data["http"]["error"]
        assert pyramid_span.data["http"]["path_tpl"] == "/response_headers"

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert (
            testenv["pyramid_server"] + "/response_headers"
            == urllib3_span.data["http"]["url"]
        )
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # custom headers
        assert "X-Capture-This" in pyramid_span.data["http"]["header"]
        assert pyramid_span.data["http"]["header"]["X-Capture-This"] == "Ok"
        assert "X-Capture-That" in pyramid_span.data["http"]["header"]
        assert pyramid_span.data["http"]["header"]["X-Capture-That"] == "Ok too"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_request_header_capture(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        request_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", testenv["pyramid_server"] + "/", headers=request_headers
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response.status == 200

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == pyramid_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert pyramid_span.p == urllib3_span.s

        # Synthetic
        assert not pyramid_span.sy
        assert not urllib3_span.sy
        assert not test_span.sy

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not pyramid_span.ec

        # wsgi
        assert pyramid_span.n == "wsgi"
        assert pyramid_span.data["http"]["host"] == "127.0.0.1:" + str(testenv["pyramid_port"])
        assert pyramid_span.data["http"]["url"] == "/"
        assert pyramid_span.data["http"]["method"] == "GET"
        assert pyramid_span.data["http"]["status"] == 200
        assert not pyramid_span.data["http"]["error"]
        assert pyramid_span.data["http"]["path_tpl"] == "/"

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert testenv["pyramid_server"] + "/" == urllib3_span.data["http"]["url"]
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # custom headers
        assert "X-Capture-This-Too" in pyramid_span.data["http"]["header"]
        assert pyramid_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in pyramid_span.data["http"]["header"]
        assert pyramid_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_scrub_secret_path_template(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", testenv["pyramid_server"] + "/hello_user/oswald?secret=sshhh"
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        pyramid_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert response.status == 200

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(pyramid_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(pyramid_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(pyramid_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert not get_current_span().is_recording()

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == pyramid_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert pyramid_span.p == urllib3_span.s

        # Synthetic
        assert not pyramid_span.sy
        assert not urllib3_span.sy
        assert not test_span.sy

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not pyramid_span.ec

        # wsgi
        assert pyramid_span.n == "wsgi"
        assert pyramid_span.data["http"]["host"] == "127.0.0.1:" + str(testenv["pyramid_port"])
        assert pyramid_span.data["http"]["url"] == "/hello_user/oswald"
        assert pyramid_span.data["http"]["method"] == "GET"
        assert pyramid_span.data["http"]["status"] == 200
        assert pyramid_span.data["http"]["params"] == "secret=<redacted>"
        assert not pyramid_span.data["http"]["error"]
        assert pyramid_span.data["http"]["path_tpl"] == "/hello_user/{user}"

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert (
            testenv["pyramid_server"] + pyramid_span.data["http"]["url"]
            == urllib3_span.data["http"]["url"]
        )
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1
