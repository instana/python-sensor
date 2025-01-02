# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from typing import Any, Dict, Generator, Optional
import aiohttp
import asyncio

import pytest

from instana.singletons import tracer, agent
from instana.util.ids import hex_id

import tests.apps.flask_app  # noqa: F401
import tests.apps.aiohttp_app  # noqa: F401
from tests.helpers import testenv


class TestAiohttpClient:
    async def fetch(
        self,
        session: aiohttp.client.ClientSession,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        try:
            async with session.get(url, headers=headers, params=params) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # New event loop for every test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        yield
        # teardown
        # Ensure that allow_exit_as_root has the default value"""
        agent.options.allow_exit_as_root = False

    def test_client_get(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["flask_server"] + "/")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aiohttp_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert wsgi_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not wsgi_span.ec

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 200
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_client_get_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True

        async def test():
            async with aiohttp.ClientSession() as session:
                return await self.fetch(session, testenv["flask_server"] + "/")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        wsgi_span = spans[0]
        aiohttp_span = spans[1]

        # Same traceId
        assert aiohttp_span.t == wsgi_span.t

        # Parent relationships
        assert not aiohttp_span.p
        assert wsgi_span.p == aiohttp_span.s

        # Error logging
        assert not aiohttp_span.ec
        assert not wsgi_span.ec

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 200
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(wsgi_span.t)}"

    def test_client_get_301(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["flask_server"] + "/301")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        wsgi_span1 = spans[0]
        wsgi_span2 = spans[1]
        aiohttp_span = spans[2]
        test_span = spans[3]

        # Same traceId
        traceId = test_span.t
        assert aiohttp_span.t == traceId
        assert wsgi_span1.t == traceId
        assert wsgi_span2.t == traceId

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert wsgi_span1.p == aiohttp_span.s
        assert wsgi_span2.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not wsgi_span1.ec
        assert not wsgi_span2.ec

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 200
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/301"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span2.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_client_get_405(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["flask_server"] + "/405")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aiohttp_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert wsgi_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not wsgi_span.ec

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 405
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/405"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_client_get_500(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["flask_server"] + "/500")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aiohttp_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert wsgi_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert aiohttp_span.ec == 1
        assert wsgi_span.ec == 1

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 500
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/500"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.data["http"]["error"] == "INTERNAL SERVER ERROR"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_client_get_504(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["flask_server"] + "/504")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aiohttp_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert wsgi_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert aiohttp_span.ec == 1
        assert wsgi_span.ec == 1

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 504
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/504"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.data["http"]["error"] == "GATEWAY TIMEOUT"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_client_get_with_params_to_scrub(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(
                        session, testenv["flask_server"], params={"secret": "yeah"}
                    )

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aiohttp_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert wsgi_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not wsgi_span.ec

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 200
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.data["http"]["params"] == "secret=<redacted>"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_client_response_header_capture(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This"]

        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(
                        session, testenv["flask_server"] + "/response_headers"
                    )

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aiohttp_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert wsgi_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not wsgi_span.ec

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 200
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/response_headers"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-Capture-This" in aiohttp_span.data["http"]["header"]
        assert aiohttp_span.data["http"]["header"]["X-Capture-This"] == "Ok"

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_client_error(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, "http://doesnotexist:10/")

        response = None
        try:
            response = self.loop.run_until_complete(test())
        except:
            pass

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        aiohttp_span = spans[0]
        test_span = spans[1]

        # Same traceId
        assert aiohttp_span.t == test_span.t

        # Parent relationships
        assert aiohttp_span.p == test_span.s

        # Error logging
        assert test_span.ec
        assert aiohttp_span.ec == 1

        assert aiohttp_span.n == "aiohttp-client"
        assert not aiohttp_span.data["http"]["status"]
        assert aiohttp_span.data["http"]["url"] == "http://doesnotexist:10/"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.data["http"]["error"]
        assert len(aiohttp_span.data["http"]["error"])
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert not response

    def test_client_get_tracing_off(self, mocker) -> None:
        mocker.patch(
            "instana.instrumentation.aiohttp.client.tracing_is_off",
            return_value=True,
        )

        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["flask_server"] + "/")

        response = self.loop.run_until_complete(test())
        assert response.status == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        # Span names are not "aiohttp-client"
        for span in spans:
            assert span.n != "aiohttp-client"

    def test_client_get_provided_tracing_config(self, mocker) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession(trace_configs=[]) as session:
                    return await self.fetch(session, testenv["flask_server"] + "/")

        response = self.loop.run_until_complete(test())
        assert response.status == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

    def test_client_request_header_capture(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too"]

        request_headers = {
            "X-Capture-This-Too": "Ok too",
        }

        async def test():
            with tracer.start_as_current_span("test"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(
                        session, testenv["flask_server"] + "/", headers=request_headers
                    )

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        # Same traceId
        traceId = test_span.t
        assert aiohttp_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert aiohttp_span.p == test_span.s
        assert wsgi_span.p == aiohttp_span.s

        # Error logging
        assert not test_span.ec
        assert not aiohttp_span.ec
        assert not wsgi_span.ec

        assert aiohttp_span.n == "aiohttp-client"
        assert aiohttp_span.data["http"]["status"] == 200
        assert aiohttp_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert aiohttp_span.data["http"]["method"] == "GET"
        assert aiohttp_span.stack
        assert isinstance(aiohttp_span.stack, list)
        assert len(aiohttp_span.stack) > 1

        assert "X-Capture-This-Too" in aiohttp_span.data["http"]["header"]
        assert aiohttp_span.data["http"]["header"]["X-Capture-This-Too"] == "Ok too"

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

        agent.options.extra_http_headers = original_extra_http_headers
