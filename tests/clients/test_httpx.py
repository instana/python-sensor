# (c) Copyright IBM Corp. 2025

import pytest
import httpx
from typing import Generator
import asyncio

from instana.singletons import agent, tracer
from instana.util.ids import hex_id
import tests.apps.flask_app
from tests.helpers import testenv


@pytest.mark.parametrize("request_mode", ["sync", "async"])
class TestHttpxClients:
    @classmethod
    def setup_class(cls) -> None:
        cls.client = httpx.Client()
        cls.host = "127.0.0.1"
        cls.recorder = tracer.span_processor

    def teardown_class(cls) -> None:
        cls.client.close()

    @pytest.fixture(autouse=True)
    def _resource(self, request_mode) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.recorder.clear_spans()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        yield
        # teardown
        if self.loop.is_running():
            self.loop.close()
        # Ensure that allow_exit_as_root has the default value
        agent.options.allow_exit_as_root = False

    async def get_async_response(self, path, request_method, headers) -> httpx.Response:
        """Asynchronous request function"""
        async with httpx.AsyncClient() as client:
            if request_method == "GET":
                response = await client.get(
                    testenv["flask_server"] + path, headers=headers
                )
            elif request_method == "POST":
                response = await client.post(
                    testenv["flask_server"] + path, headers=headers
                )
            return response

    # Synchronous request function
    def get_sync_response(self, path, request_method, headers) -> httpx.Response:
        """Synchronous request function"""
        if request_method == "GET":
            response = self.client.get(testenv["flask_server"] + path, headers=headers)
        elif request_method == "POST":
            response = self.client.post(testenv["flask_server"] + path, headers=headers)
        return response

    def execute_request(
        self, request_mode, path, request_method="GET", headers=None
    ) -> httpx.Response:
        if request_mode == "async":
            res = self.loop.run_until_complete(
                self.get_async_response(path, request_method, headers)
            )
        elif request_mode == "sync":
            res = self.get_sync_response(path, request_method, headers)
        return res

    def test_get_request(self, request_mode) -> None:
        path = "/"
        with tracer.start_as_current_span("test"):
            res = self.execute_request(request_mode, path)

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

    def test_get_request_as_root_exit_span(self, request_mode) -> None:
        path = "/"
        agent.options.allow_exit_as_root = True
        res = self.execute_request(request_mode, path)

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
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == testenv["flask_server"] + path
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

    def test_get_request_with_query(self, request_mode) -> None:
        path = "/"
        with tracer.start_as_current_span("test"):
            res = self.execute_request(
                request_mode, path + "?user=instana&pass=itsasecret"
            )

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
        assert httpx_span.data["http"]["params"] == "user=instana&pass=<redacted>"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

    def test_post_request(self, request_mode) -> None:
        path = "/notfound"
        with tracer.start_as_current_span("test"):
            res = self.execute_request(request_mode, path, request_method="POST")

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

    def test_5xx_request(self, request_mode) -> None:
        path = "/500"
        with tracer.start_as_current_span("test"):
            res = self.execute_request(request_mode, path)

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

    def test_response_header_capture(self, request_mode) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]
        path = "/response_headers"

        with tracer.start_as_current_span("test"):
            res = self.execute_request(request_mode, path)

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

    def test_request_header_capture(self, request_mode) -> None:
        path = "/"
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        request_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }
        with tracer.start_as_current_span("test"):
            res = self.execute_request(request_mode, path, headers=request_headers)

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
