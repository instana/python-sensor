# (c) Copyright IBM Corp. 2025

import pytest
import httpx
from typing import Generator

from instana.singletons import agent, tracer
from instana.util.ids import hex_id
import tests.apps.flask_app
from tests.helpers import testenv


class TestHttpx:
    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.host = "127.0.0.1"
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        yield
        # teardown
        # Ensure that allow_exit_as_root has the default value
        agent.options.allow_exit_as_root = False

    def test_get_request(self):
        with tracer.start_as_current_span("test"):
            res = httpx.get(testenv["flask_server"] + "/")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        httpx_span = spans[1]
        test_span = spans[2]

        assert res
        assert res.status_code == 200

        assert "X-INSTANA-T" in res.headers
        assert int(res.headers["X-INSTANA-T"], 16)
        assert res.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in res.headers
        assert int(res.headers["X-INSTANA-S"], 16)
        assert res.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in res.headers
        assert res.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in res.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert res.headers["Server-Timing"] == server_timing_value

        # Same traceId
        assert test_span.t == httpx_span.t
        assert httpx_span.t == wsgi_span.t

        # Parent relationships
        assert httpx_span.p == test_span.s
        assert wsgi_span.p == httpx_span.s

        # Error logging
        assert not test_span.ec
        assert not httpx_span.ec
        assert not wsgi_span.ec

        # span names
        assert wsgi_span.n == "wsgi"
        assert test_span.data["sdk"]["name"] == "test"
        assert httpx_span.n == "http"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.host
        assert httpx_span.data["http"]["path"] == "/"
        assert httpx_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

    def test_get_request_as_root_exit_span(self):
        agent.options.allow_exit_as_root = True
        res = httpx.get(testenv["flask_server"] + "/")

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        wsgi_span = spans[0]
        httpx_span = spans[1]

        assert res
        assert res.status_code == 200

        assert "X-INSTANA-T" in res.headers
        assert int(res.headers["X-INSTANA-T"], 16)
        assert res.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in res.headers
        assert int(res.headers["X-INSTANA-S"], 16)
        assert res.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in res.headers
        assert res.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in res.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert res.headers["Server-Timing"] == server_timing_value

        # Same traceId
        assert httpx_span.t == wsgi_span.t

        # Parent relationships
        assert not httpx_span.p
        assert wsgi_span.p == httpx_span.s

        # Error logging
        assert not httpx_span.ec
        assert not wsgi_span.ec

        # span names
        assert wsgi_span.n == "wsgi"
        assert httpx_span.n == "http"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.host
        assert httpx_span.data["http"]["path"] == "/"
        assert httpx_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

    def test_get_request_with_query(self):
        with tracer.start_as_current_span("test"):
            res = httpx.get(testenv["flask_server"] + "/?user=instana&pass=itsasecret")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        httpx_span = spans[1]
        test_span = spans[2]

        assert res
        assert res.status_code == 200

        # Same traceId
        assert test_span.t == httpx_span.t
        assert httpx_span.t == wsgi_span.t

        # Parent relationships
        assert httpx_span.p == test_span.s
        assert wsgi_span.p == httpx_span.s

        # Error logging
        assert not test_span.ec
        assert not httpx_span.ec
        assert not wsgi_span.ec

        # span names
        assert wsgi_span.n == "wsgi"
        assert test_span.data["sdk"]["name"] == "test"
        assert httpx_span.n == "http"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.host
        assert httpx_span.data["http"]["path"] == "/"
        assert httpx_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert httpx_span.data["http"]["params"] == "user=instana&pass=<redacted>"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

    def test_post_request(self):
        path = "/notfound"
        with tracer.start_as_current_span("test"):
            res = httpx.post(testenv["flask_server"] + "/notfound")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        httpx_span = spans[1]
        test_span = spans[2]

        assert res
        assert res.status_code == 404

        # Same traceId
        assert test_span.t == httpx_span.t
        assert httpx_span.t == wsgi_span.t

        # Parent relationships
        assert httpx_span.p == test_span.s
        assert wsgi_span.p == httpx_span.s

        # Error logging
        assert not test_span.ec
        assert not httpx_span.ec
        assert not wsgi_span.ec

        # span names
        assert wsgi_span.n == "wsgi"
        assert test_span.data["sdk"]["name"] == "test"
        assert httpx_span.n == "http"

        # httpx
        assert httpx_span.data["http"]["status"] == 404
        assert httpx_span.data["http"]["host"] == self.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == testenv["flask_server"] + path
        assert httpx_span.data["http"]["method"] == "POST"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

    def test_5xx_request(self):
        path = "/500"
        with tracer.start_as_current_span("test"):
            res = httpx.get(testenv["flask_server"] + path)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        httpx_span = spans[1]
        test_span = spans[2]

        assert res
        assert res.status_code == 500

        assert "X-INSTANA-T" in res.headers
        assert int(res.headers["X-INSTANA-T"], 16)
        assert res.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in res.headers
        assert int(res.headers["X-INSTANA-S"], 16)
        assert res.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in res.headers
        assert res.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in res.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert res.headers["Server-Timing"] == server_timing_value

        # Same traceId
        assert test_span.t == httpx_span.t
        assert httpx_span.t == wsgi_span.t

        # Parent relationships
        assert httpx_span.p == test_span.s
        assert wsgi_span.p == httpx_span.s

        # Error logging
        assert not test_span.ec
        assert httpx_span.ec == 1
        assert wsgi_span.ec == 1

        # span names
        assert wsgi_span.n == "wsgi"
        assert test_span.data["sdk"]["name"] == "test"
        assert httpx_span.n == "http"

        # httpx
        assert httpx_span.data["http"]["status"] == 500
        assert httpx_span.data["http"]["host"] == self.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == testenv["flask_server"] + path
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

    def test_response_header_capture(self):
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]
        path = "/response_headers"

        with tracer.start_as_current_span("test"):
            res = httpx.get(testenv["flask_server"] + path)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        httpx_span = spans[1]
        test_span = spans[2]

        assert res
        assert res.status_code == 200

        # Same traceId
        assert test_span.t == httpx_span.t
        assert httpx_span.t == wsgi_span.t

        # Parent relationships
        assert httpx_span.p == test_span.s
        assert wsgi_span.p == httpx_span.s

        # Error logging
        assert not test_span.ec
        assert not httpx_span.ec
        assert not wsgi_span.ec

        # span names
        assert wsgi_span.n == "wsgi"
        assert test_span.data["sdk"]["name"] == "test"
        assert httpx_span.n == "http"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == testenv["flask_server"] + path
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        assert "X-Capture-This" in httpx_span.data["http"]["header"]
        assert httpx_span.data["http"]["header"]["X-Capture-This"] == "Ok"
        assert "X-Capture-That" in httpx_span.data["http"]["header"]
        assert httpx_span.data["http"]["header"]["X-Capture-That"] == "Ok too"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_request_header_capture(self):
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        request_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }
        with tracer.start_as_current_span("test"):
            res = httpx.get(testenv["flask_server"] + "/", headers=request_headers)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        httpx_span = spans[1]
        test_span = spans[2]

        assert res
        assert res.status_code == 200

        # Same traceId
        assert test_span.t == httpx_span.t
        assert httpx_span.t == wsgi_span.t

        # Parent relationships
        assert httpx_span.p == test_span.s
        assert wsgi_span.p == httpx_span.s

        # Error logging
        assert not test_span.ec
        assert not httpx_span.ec
        assert not wsgi_span.ec

        # span names
        assert wsgi_span.n == "wsgi"
        assert test_span.data["sdk"]["name"] == "test"
        assert httpx_span.n == "http"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.host
        assert httpx_span.data["http"]["path"] == "/"
        assert httpx_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        assert "X-Capture-This-Too" in httpx_span.data["http"]["header"]
        assert httpx_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in httpx_span.data["http"]["header"]
        assert httpx_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

        agent.options.extra_http_headers = original_extra_http_headers
