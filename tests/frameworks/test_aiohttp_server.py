# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import asyncio
from typing import Generator

import aiohttp
import pytest

from instana.singletons import agent, tracer
from instana.util.ids import hex_id
from tests.helpers import testenv


class TestAiohttpServer:
    async def fetch(self, session, url, headers=None, params=None):
        try:
            async with session.get(url, headers=headers, params=params) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Load test server application
        import tests.apps.aiohttp_app  # noqa: F401

        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # New event loop for every test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        yield

    def test_server_get(self):
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aioclient_span.t == traceId
        assert aioserver_span.t == traceId

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s

        # Synthetic
        assert not test_span.sy
        assert not aioclient_span.sy
        assert not aioserver_span.sy

        # Error logging
        assert not test_span.ec
        assert not aioclient_span.ec
        assert not aioserver_span.ec

        assert aioserver_span.n == "aiohttp-server"
        assert aioserver_span.data["http"]["status"] == 200
        assert aioserver_span.data["http"]["url"] == f"{testenv['aiohttp_server']}/"
        assert aioserver_span.data["http"]["method"] == "GET"
        assert not aioserver_span.stack

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_server_get_204(self):
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/204")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        trace_id = test_span.t
        assert aioclient_span.t == trace_id
        assert aioserver_span.t == trace_id

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s

        # Synthetic
        assert not test_span.sy
        assert not aioclient_span.sy
        assert not aioserver_span.sy

        # Error logging
        assert not test_span.ec
        assert not aioclient_span.ec
        assert not aioserver_span.ec

        assert aioserver_span.n == "aiohttp-server"
        assert aioserver_span.data["http"]["status"] == 204
        assert aioserver_span.data["http"]["url"] == f"{testenv['aiohttp_server']}/204"
        assert aioserver_span.data["http"]["method"] == "GET"
        assert not aioserver_span.stack

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(trace_id)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(trace_id)}"

    def test_server_synthetic_request(self):
        async def test():
            headers = {"X-INSTANA-SYNTHETIC": "1"}

            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(
                        session, testenv["aiohttp_server"] + "/", headers=headers
                    )

        response = self.loop.run_until_complete(test())
        assert response

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        assert aioserver_span.sy
        assert not aioclient_span.sy
        assert not test_span.sy

    def test_server_get_with_params_to_scrub(self):
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(
                        session,
                        testenv["aiohttp_server"],
                        params={"secret": "iloveyou"},
                    )

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aioclient_span.t == traceId
        assert aioserver_span.t == traceId

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s

        # Error logging
        assert not test_span.ec
        assert not aioclient_span.ec
        assert not aioserver_span.ec

        assert aioserver_span.n == "aiohttp-server"
        assert aioserver_span.data["http"]["status"] == 200
        assert aioserver_span.data["http"]["url"] == f"{testenv['aiohttp_server']}/"
        assert aioserver_span.data["http"]["method"] == "GET"
        assert aioserver_span.data["http"]["params"] == "secret=<redacted>"
        assert not aioserver_span.stack

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_server_request_header_capture(self):
        original_extra_http_headers = agent.options.extra_http_headers

        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    # Hack together a manual custom headers list
                    agent.options.extra_http_headers = [
                        "X-Capture-This",
                        "X-Capture-That",
                    ]

                    headers = dict()
                    headers["X-Capture-This"] = "this"
                    headers["X-Capture-That"] = "that"

                    return await self.fetch(
                        session,
                        testenv["aiohttp_server"],
                        headers=headers,
                        params={"secret": "iloveyou"},
                    )

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aioclient_span.t == traceId
        assert aioserver_span.t == traceId

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s

        # Error logging
        assert not test_span.ec
        assert not aioclient_span.ec
        assert not aioserver_span.ec

        assert aioserver_span.n == "aiohttp-server"
        assert aioserver_span.data["http"]["status"] == 200
        assert aioserver_span.data["http"]["url"] == f"{testenv['aiohttp_server']}/"
        assert aioserver_span.data["http"]["method"] == "GET"
        assert aioserver_span.data["http"]["params"] == "secret=<redacted>"
        assert not aioserver_span.stack

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

        assert "X-Capture-This" in aioserver_span.data["http"]["header"]
        assert aioserver_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert "X-Capture-That" in aioserver_span.data["http"]["header"]
        assert aioserver_span.data["http"]["header"]["X-Capture-That"] == "that"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_server_response_header_capture(self):
        original_extra_http_headers = agent.options.extra_http_headers

        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    # Hack together a manual custom headers list
                    agent.options.extra_http_headers = [
                        "X-Capture-This-Too",
                        "X-Capture-That-Too",
                    ]

                    return await self.fetch(
                        session,
                        testenv["aiohttp_server"] + "/response_headers"
                    )

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aioclient_span.t == traceId
        assert aioserver_span.t == traceId

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s

        # Error logging
        assert not test_span.ec
        assert not aioclient_span.ec
        assert not aioserver_span.ec

        assert aioserver_span.n == "aiohttp-server"
        assert aioserver_span.data["http"]["status"] == 200
        assert aioserver_span.data["http"]["url"] == f"{testenv['aiohttp_server']}/response_headers"
        assert aioserver_span.data["http"]["method"] == "GET"
        assert not aioserver_span.stack

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

        assert "X-Capture-This-Too" in aioserver_span.data["http"]["header"]
        assert aioserver_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in aioserver_span.data["http"]["header"]
        assert aioserver_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_server_get_401(self):
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/401")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aioclient_span.t == traceId
        assert aioserver_span.t == traceId

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s

        # Error logging
        assert not test_span.ec
        assert not aioclient_span.ec
        assert not aioserver_span.ec

        assert aioserver_span.n == "aiohttp-server"
        assert aioserver_span.data["http"]["status"] == 401
        assert aioserver_span.data["http"]["url"] == f"{testenv['aiohttp_server']}/401"
        assert aioserver_span.data["http"]["method"] == "GET"
        assert not aioserver_span.stack

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_server_get_500(self):
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/500")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aioclient_span.t == traceId
        assert aioserver_span.t == traceId

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s

        # Error logging
        assert not test_span.ec
        assert aioclient_span.ec == 1
        assert aioserver_span.ec == 1

        assert aioserver_span.n == "aiohttp-server"
        assert aioserver_span.data["http"]["status"] == 500
        assert aioserver_span.data["http"]["url"] == f"{testenv['aiohttp_server']}/500"
        assert aioserver_span.data["http"]["method"] == "GET"
        assert not aioserver_span.stack

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_server_get_exception(self):
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(
                        session, testenv["aiohttp_server"] + "/exception"
                    )

        response = self.loop.run_until_complete(test())
        assert response

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aioclient_span.t == traceId
        assert aioserver_span.t == traceId

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s

        # Error logging
        assert not test_span.ec
        assert aioclient_span.ec == 1
        assert aioserver_span.ec == 1

        assert aioserver_span.n == "aiohttp-server"
        assert aioserver_span.data["http"]["status"] == 500
        assert (
            aioserver_span.data["http"]["url"]
            == f"{testenv['aiohttp_server']}/exception"
        )
        assert aioserver_span.data["http"]["method"] == "GET"
        assert not aioserver_span.stack

        assert aioclient_span.n == "aiohttp-client"
        assert aioclient_span.data["http"]["status"] == 500
        assert aioclient_span.data["http"]["error"] == "Internal Server Error"
        assert aioclient_span.stack
        assert isinstance(aioclient_span.stack, list)
        assert len(aioclient_span.stack) > 1


class TestAiohttpServerMiddleware:
    async def fetch(self, session, url, headers=None, params=None):
        try:
            async with session.get(url, headers=headers, params=params) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Load test server application
        import tests.apps.aiohttp_app2  # noqa: F401

        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # New event loop for every test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        yield

    def test_server_get(self):
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/")

        response = self.loop.run_until_complete(test())
        assert response

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aioclient_span.t == traceId
        assert aioserver_span.t == traceId

        # Parent relationships
        assert aioclient_span.p == test_span.s
        assert aioserver_span.p == aioclient_span.s
