from __future__ import absolute_import

import aiohttp
import asyncio
import unittest

from instana.singletons import async_tracer

class TestAiohttp(unittest.TestCase):
    async def connect(self):
        pass

    async def fetch(self, session, url):
        async with session.get(url) as response:
            return response

    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = async_tracer.recorder
        self.recorder.clear_spans()

        # New event loop for every test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.loop.run_until_complete(self.connect())

    def tearDown(self):
        """ Purge the queue """
        pass

    def test_get(self):
        response = None

        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, 'http://127.0.0.1:5000/')

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, wsgi_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aiohttp_span.error)
        self.assertIsNone(aiohttp_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertIsNone(wsgi_span.ec)

        self.assertEqual("aiohttp", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], wsgi_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_500(self):
        response = None

        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, 'http://127.0.0.1:5000/500')

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, wsgi_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertTrue(aiohttp_span.error)
        self.assertEqual(aiohttp_span.ec, 1)
        self.assertTrue(wsgi_span.error)
        self.assertEqual(wsgi_span.ec, 1)

        self.assertEqual("aiohttp", aiohttp_span.n)
        self.assertEqual(500, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/500", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertEqual('INTERNAL SERVER ERROR', aiohttp_span.data.http.error)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], wsgi_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_504(self):
        response = None

        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, 'http://127.0.0.1:5000/504')

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, wsgi_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertTrue(aiohttp_span.error)
        self.assertEqual(aiohttp_span.ec, 1)
        self.assertTrue(wsgi_span.error)
        self.assertEqual(wsgi_span.ec, 1)

        self.assertEqual("aiohttp", aiohttp_span.n)
        self.assertEqual(504, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/504", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertEqual('GATEWAY TIMEOUT', aiohttp_span.data.http.error)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], wsgi_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_with_params(self):
        response = None

        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, 'http://127.0.0.1:5000/?ok=yeah')

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        wsgi_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, wsgi_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(wsgi_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aiohttp_span.error)
        self.assertIsNone(aiohttp_span.ec)
        self.assertFalse(wsgi_span.error)
        self.assertIsNone(wsgi_span.ec)

        self.assertEqual("aiohttp", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertEqual("ok=yeah", aiohttp_span.data.http.params)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], wsgi_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)


