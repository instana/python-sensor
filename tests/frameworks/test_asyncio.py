# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import asyncio
from typing import Any, Dict, Generator, Optional

import aiohttp
import pytest

import tests.apps.flask_app  # noqa: F401
from instana.configurator import config
from instana.singletons import tracer
from tests.helpers import testenv


class TestAsyncio:
    async def fetch(
        self,
        session: aiohttp.ClientSession,
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

        # Restore default
        config["asyncio_task_context_propagation"]["enabled"] = False
        yield
        # teardown
        # Close the loop if running
        if self.loop.is_running():
            self.loop.close()

    def test_ensure_future_with_context(self) -> None:
        async def run_later(msg="Hello"):
            async with aiohttp.ClientSession() as session:
                return await self.fetch(session, testenv["flask_server"] + "/")

        async def test():
            with tracer.start_as_current_span("test"):
                asyncio.ensure_future(run_later("Hello OTel"))
            await asyncio.sleep(0.5)

        # Override default task context propagation
        config["asyncio_task_context_propagation"]["enabled"] = True

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = spans[0]
        wsgi_span = spans[1]
        aioclient_span = spans[2]

        assert test_span.t == wsgi_span.t
        assert aioclient_span.t == test_span.t

        assert not test_span.p
        assert wsgi_span.p == aioclient_span.s
        assert aioclient_span.p == test_span.s

    def test_ensure_future_without_context(self) -> None:
        async def run_later(msg="Hello"):
            async with aiohttp.ClientSession() as session:
                return await self.fetch(session, testenv["flask_server"] + "/")

        async def test():
            with tracer.start_as_current_span("test"):
                asyncio.ensure_future(run_later("Hello OTel"))
            await asyncio.sleep(0.5)

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()

        assert len(spans) == 2
        assert spans[0].n == "sdk"
        assert spans[1].n == "wsgi"

        # Without the context propagated, we should get two separate traces
        assert spans[0].t != spans[1].t

    if hasattr(asyncio, "create_task"):

        def test_create_task_with_context(self) -> None:
            async def run_later(msg="Hello"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["flask_server"] + "/")

            async def test():
                with tracer.start_as_current_span("test"):
                    asyncio.create_task(run_later("Hello OTel"))
                await asyncio.sleep(0.5)

            # Override default task context propagation
            config["asyncio_task_context_propagation"]["enabled"] = True

            self.loop.run_until_complete(test())

            spans = self.recorder.queued_spans()
            assert len(spans) == 3

            test_span = spans[0]
            wsgi_span = spans[1]
            aioclient_span = spans[2]

            assert wsgi_span.t == test_span.t
            assert aioclient_span.t == test_span.t

            assert not test_span.p
            assert wsgi_span.p == aioclient_span.s
            assert aioclient_span.p == test_span.s

        def test_create_task_without_context(self) -> None:
            async def run_later(msg="Hello"):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["flask_server"] + "/")

            async def test():
                with tracer.start_as_current_span("test"):
                    asyncio.create_task(run_later("Hello OTel"))
                await asyncio.sleep(0.5)

            self.loop.run_until_complete(test())

            spans = self.recorder.queued_spans()

            assert len(spans) == 2
            assert spans[0].n == "sdk"
            assert spans[1].n == "wsgi"

            # Without the context propagated, we should get two separate traces
            assert spans[0].t != spans[1].t
