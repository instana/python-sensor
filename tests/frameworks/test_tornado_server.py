# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import pytest
from typing import Generator

import asyncio
import aiohttp
import tornado
from tornado.httpclient import AsyncHTTPClient

from instana.util.ids import hex_id
import tests.apps.tornado_server

from instana.singletons import tracer, agent
from tests.helpers import testenv, get_first_span_by_name, get_first_span_by_filter
from instana.span.span import get_current_span


class TestTornadoServer:
    async def fetch(self, session, url, headers=None, params=None):
        try:
            async with session.get(url, headers=headers, params=params) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    async def post(self, session, url, headers=None):
        try:
            async with session.post(url, headers=headers, data={"hello": "post"}) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """ Clear all spans before a test run """
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # New event loop for every test
        # self.loop = tornado.ioloop.IOLoop.current()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.http_client = AsyncHTTPClient()
        yield
        self.http_client.close()

    def test_get(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_span.p == aiohttp_span.s

        # Synthetic
        assert not tornado_span.sy
        assert not aiohttp_span.sy
        assert not test_span.sy

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not tornado_span.ec

        assert tornado_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == tornado_span.data["http"]["url"]
        assert not tornado_span.data["http"]["params"]
        assert tornado_span.data["http"]["method"] == "GET"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_post(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.post(session, testenv["tornado_server"] + "/")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert not get_current_span().is_recording()

        assert tornado_span.n == "tornado-server"
        assert aiohttp_span.n == "aiohttp-client"
        assert test_span.n == "sdk"

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not tornado_span.ec

        assert tornado_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == tornado_span.data["http"]["url"]
        assert not tornado_span.data["http"]["params"]
        assert tornado_span.data["http"]["method"] == "POST"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "POST"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_synthetic_request(self) -> None:
        async def test():
            headers = {
                'X-INSTANA-SYNTHETIC': '1'
            }

            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/", headers=headers)

        tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span.sy
        assert not aiohttp_span.sy
        assert not test_span.sy

    def test_get_301(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/301")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        filter = lambda span: span.n == "tornado-server" and span.data["http"]["status"] == 301
        tornado_301_span = get_first_span_by_filter(spans, filter)
        filter = lambda span: span.n == "tornado-server" and span.data["http"]["status"] == 200
        tornado_span = get_first_span_by_filter(spans, filter)
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_301_span
        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert not get_current_span().is_recording()

        assert tornado_301_span.n == "tornado-server"
        assert tornado_span.n == "tornado-server"
        assert aiohttp_span.n == "aiohttp-client"
        assert test_span.n == "sdk"

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t
        assert traceId == tornado_301_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_301_span.p == aiohttp_span.s
        assert tornado_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not tornado_301_span.ec
        assert not tornado_span.ec

        assert tornado_301_span.data["http"]["status"] == 301
        assert testenv["tornado_server"] + "/301" == tornado_301_span.data["http"]["url"]
        assert not tornado_span.data["http"]["params"]
        assert tornado_301_span.data["http"]["method"] == "GET"
        assert not tornado_301_span.stack

        assert tornado_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == tornado_span.data["http"]["url"]
        assert tornado_span.data["http"]["method"] == "GET"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/301" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    @pytest.mark.skip("Non deterministic (flaky) testcase")
    def test_get_405(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/405")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert not get_current_span().is_recording()

        assert tornado_span.n == "tornado-server"
        assert aiohttp_span.n == "aiohttp-client"
        assert test_span.n == "sdk"

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not tornado_span.ec

        assert tornado_span.data["http"]["status"] == 405
        assert testenv["tornado_server"] + "/405" == tornado_span.data["http"]["url"]
        assert not tornado_span.data["http"]["params"]
        assert tornado_span.data["http"]["method"] == "GET"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 405
        assert testenv["tornado_server"] + "/405" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    @pytest.mark.skip("Non deterministic (flaky) testcase")
    def test_get_500(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/500")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert not get_current_span().is_recording()

        assert tornado_span.n == "tornado-server"
        assert aiohttp_span.n == "aiohttp-client"
        assert test_span.n == "sdk"

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert aiohttp_span.ec == 1
        assert tornado_span.ec == 1

        assert tornado_span.data["http"]["status"] == 500
        assert testenv["tornado_server"] + "/500" == tornado_span.data["http"]["url"]
        assert not tornado_span.data["http"]["params"]
        assert tornado_span.data["http"]["method"] == "GET"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 500
        assert testenv["tornado_server"] + "/500" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert 'Internal Server Error' == aiohttp_span.data["http"]["error"]
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    @pytest.mark.skip("Non deterministic (flaky) testcase")
    def test_get_504(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/504")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert not get_current_span().is_recording()

        assert tornado_span.n == "tornado-server"
        assert aiohttp_span.n == "aiohttp-client"
        assert test_span.n == "sdk"

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert aiohttp_span.ec == 1
        assert tornado_span.ec == 1

        assert tornado_span.data["http"]["status"] == 504
        assert testenv["tornado_server"] + "/504" == tornado_span.data["http"]["url"]
        assert not tornado_span.data["http"]["params"]
        assert tornado_span.data["http"]["method"] == "GET"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 504
        assert testenv["tornado_server"] + "/504" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert 'Gateway Timeout' == aiohttp_span.data["http"]["error"]
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_get_with_params_to_scrub(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"], params={"secret": "yeah"})

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        assert not get_current_span().is_recording()

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert tornado_span.n == "tornado-server"
        assert aiohttp_span.n == "aiohttp-client"
        assert test_span.n == "sdk"

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not tornado_span.ec

        assert tornado_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == tornado_span.data["http"]["url"]
        assert tornado_span.data["http"]["params"] == "secret=<redacted>"
        assert tornado_span.data["http"]["method"] == "GET"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.data["http"]["params"] == "secret=<redacted>"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_request_header_capture(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    # Hack together a manual custom request headers list
                    agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

                    request_headers = {
                        "X-Capture-This": "this",
                        "X-Capture-That": "that"
                    }

                    return await self.fetch(session, testenv["tornado_server"], headers=request_headers, params={"secret": "iloveyou"})

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert not get_current_span().is_recording()

        assert tornado_span.n == "tornado-server"
        assert aiohttp_span.n == "aiohttp-client"
        assert test_span.n == "sdk"

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not tornado_span.ec

        assert tornado_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == tornado_span.data["http"]["url"]
        assert tornado_span.data["http"]["params"] == "secret=<redacted>"
        assert tornado_span.data["http"]["method"] == "GET"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.data["http"]["params"] == "secret=<redacted>"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

        assert "X-Capture-This" in tornado_span.data["http"]["header"]
        assert tornado_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert "X-Capture-That" in tornado_span.data["http"]["header"]
        assert tornado_span.data["http"]["header"]["X-Capture-That"] == "that"

    def test_response_header_capture(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    # Hack together a manual custom response headers list
                    agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

                    return await self.fetch(session, testenv["tornado_server"] + "/response_headers", params={"secret": "itsasecret"})

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert tornado_span
        assert aiohttp_span
        assert test_span

        assert not get_current_span().is_recording()

        assert tornado_span.n == "tornado-server"
        assert aiohttp_span.n == "aiohttp-client"
        assert test_span.n == "sdk"

        # Same traceId
        traceId = test_span.t
        assert traceId == aiohttp_span.t
        assert traceId == tornado_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert tornado_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not tornado_span.ec

        assert tornado_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/response_headers" == tornado_span.data["http"]["url"]
        assert tornado_span.data["http"]["params"] == "secret=<redacted>"
        assert tornado_span.data["http"]["method"] == "GET"
        assert not tornado_span.stack

        assert aiohttp_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/response_headers" == aiohttp_span.data["http"]["url"]
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.data["http"]["params"] == "secret=<redacted>"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(tornado_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

        assert "X-Capture-This-Too" in tornado_span.data["http"]["header"]
        assert tornado_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in tornado_span.data["http"]["header"]
        assert tornado_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"
