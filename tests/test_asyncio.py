from __future__ import absolute_import

import asyncio
import unittest

import aiohttp

from instana.singletons import async_tracer

from .helpers import testenv


class TestAsyncio(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = async_tracer.recorder
        self.recorder.clear_spans()

        # New event loop for every test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        """ Purge the queue """
        pass

    async def fetch(self, session, url, headers=None):
        try:
            async with session.get(url, headers=headers) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    def test_ensure_future(self):
        async def run_later(msg="Hello"):
            # print("run_later: %s" % async_tracer.active_span.operation_name)
            async with aiohttp.ClientSession() as session:
                return await self.fetch(session, testenv["wsgi_server"] + "/")

        async def test():
            with async_tracer.start_active_span('test'):
                asyncio.ensure_future(run_later("Hello"))
            await asyncio.sleep(0.5)

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = spans[0]
        wsgi_span = spans[1]
        aioclient_span = spans[2]

        self.assertEqual(test_span.t, wsgi_span.t)
        self.assertEqual(test_span.t, aioclient_span.t)

        self.assertEqual(test_span.p, None)
        self.assertEqual(wsgi_span.p, aioclient_span.s)
        self.assertEqual(aioclient_span.p, test_span.s)

    def test_ensure_future_without_context(self):
        async def run_later(msg="Hello"):
            # print("run_later: %s" % async_tracer.active_span.operation_name)
            async with aiohttp.ClientSession() as session:
                return await self.fetch(session, testenv["wsgi_server"] + "/")

        async def test():
            asyncio.ensure_future(run_later("Hello"))
            await asyncio.sleep(0.5)

        self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()

        # Only the WSGI webserver generated a span (entry span)
        self.assertEqual(1, len(spans))
        self.assertEqual("wsgi", spans[0].n)
