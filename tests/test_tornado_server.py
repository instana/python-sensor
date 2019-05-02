from __future__ import absolute_import


import asyncio
import aiohttp
import unittest

import tornado
from tornado.httpclient import AsyncHTTPClient

from instana.singletons import async_tracer, agent

from .helpers import testenv


class TestTornadoServer(unittest.TestCase):
    async def fetch(self, session, url, headers=None):
        try:
            async with session.get(url, headers=headers) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    async def post(self, session, url, headers=None):
        try:
            async with session.post(url, headers=headers, data={"hello": "post"}) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = async_tracer.recorder
        self.recorder.clear_spans()

        self.http_client = AsyncHTTPClient()

        # New event loop for every test
        # self.loop = tornado.ioloop.IOLoop.current()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.http_client.close()

    def test_get(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aiohttp_span.error)
        self.assertIsNone(aiohttp_span.ec)
        self.assertFalse(tornado_span.error)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual(200, tornado_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_span.data.http.host)
        self.assertEqual("/", tornado_span.data.http.path)
        self.assertIsNone(tornado_span.data.http.params)
        self.assertEqual("GET", tornado_span.data.http.method)
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:4133/", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_post(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.post(session, testenv["tornado_server"] + "/")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aiohttp_span.error)
        self.assertIsNone(aiohttp_span.ec)
        self.assertFalse(tornado_span.error)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual(200, tornado_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_span.data.http.host)
        self.assertEqual("/", tornado_span.data.http.path)
        self.assertIsNone(tornado_span.data.http.params)
        self.assertEqual("POST", tornado_span.data.http.method)
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:4133/", aiohttp_span.data.http.url)
        self.assertEqual("POST", aiohttp_span.data.http.method)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_301(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/301")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        tornado_301_span = spans[0]
        tornado_span = spans[1]
        aiohttp_span = spans[2]
        test_span = spans[3]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)
        self.assertEqual(traceId, tornado_301_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_301_span.p, aiohttp_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aiohttp_span.error)
        self.assertIsNone(aiohttp_span.ec)
        self.assertFalse(tornado_301_span.error)
        self.assertIsNone(tornado_301_span.ec)
        self.assertFalse(tornado_span.error)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual("tornado-server", tornado_301_span.n)
        self.assertEqual(301, tornado_301_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_301_span.data.http.host)
        self.assertEqual("/301", tornado_301_span.data.http.path)
        self.assertIsNone(tornado_span.data.http.params)
        self.assertEqual("GET", tornado_301_span.data.http.method)
        self.assertIsNotNone(tornado_301_span.stack)
        self.assertTrue(type(tornado_301_span.stack) is list)
        self.assertTrue(len(tornado_301_span.stack) > 1)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual(200, tornado_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_span.data.http.host)
        self.assertEqual("/", tornado_span.data.http.path)
        self.assertEqual("GET", tornado_span.data.http.method)
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:4133/301", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_405(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/405")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aiohttp_span.error)
        self.assertIsNone(aiohttp_span.ec)
        self.assertFalse(tornado_span.error)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual(405, tornado_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_span.data.http.host)
        self.assertEqual("/405", tornado_span.data.http.path)
        self.assertIsNone(tornado_span.data.http.params)
        self.assertEqual("GET", tornado_span.data.http.method)
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(405, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:4133/405", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_500(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/500")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertTrue(aiohttp_span.error)
        self.assertEqual(aiohttp_span.ec, 1)
        self.assertTrue(tornado_span.error)
        self.assertEqual(tornado_span.ec, 1)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual(500, tornado_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_span.data.http.host)
        self.assertEqual("/500", tornado_span.data.http.path)
        self.assertIsNone(tornado_span.data.http.params)
        self.assertEqual("GET", tornado_span.data.http.method)
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(500, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:4133/500", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertEqual('Internal Server Error', aiohttp_span.data.http.error)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_504(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/504")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertTrue(aiohttp_span.error)
        self.assertEqual(aiohttp_span.ec, 1)
        self.assertTrue(tornado_span.error)
        self.assertEqual(tornado_span.ec, 1)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual(504, tornado_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_span.data.http.host)
        self.assertEqual("/504", tornado_span.data.http.path)
        self.assertIsNone(tornado_span.data.http.params)
        self.assertEqual("GET", tornado_span.data.http.method)
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(504, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:4133/504", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertEqual('Gateway Timeout', aiohttp_span.data.http.error)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_with_params_to_scrub(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/?secret=yeah")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = spans[0]
        aiohttp_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aiohttp_span.error)
        self.assertIsNone(aiohttp_span.ec)
        self.assertFalse(tornado_span.error)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual(200, tornado_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_span.data.http.host)
        self.assertEqual("/", tornado_span.data.http.path)
        self.assertEqual("secret=<redacted>", tornado_span.data.http.params)
        self.assertEqual("GET", tornado_span.data.http.method)
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:4133/", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertEqual("secret=<redacted>", aiohttp_span.data.http.params)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_custom_header_capture(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    # Hack together a manual custom headers list
                    agent.extra_headers = [u'X-Capture-This', u'X-Capture-That']

                    headers = dict()
                    headers['X-Capture-This'] = 'this'
                    headers['X-Capture-That'] = 'that'

                    return await self.fetch(session, testenv["tornado_server"] + "/?secret=iloveyou", headers=headers)

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aioclient_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aioclient_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aioclient_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aioclient_span.error)
        self.assertIsNone(aioclient_span.ec)
        self.assertFalse(tornado_span.error)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual(200, tornado_span.data.http.status)
        self.assertEqual("127.0.0.1:4133", tornado_span.data.http.host)
        self.assertEqual("/", tornado_span.data.http.path)
        self.assertEqual("secret=<redacted>", tornado_span.data.http.params)
        self.assertEqual("GET", tornado_span.data.http.method)
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual("aiohttp-client", aioclient_span.n)
        self.assertEqual(200, aioclient_span.data.http.status)
        self.assertEqual("http://127.0.0.1:4133/", aioclient_span.data.http.url)
        self.assertEqual("GET", aioclient_span.data.http.method)
        self.assertEqual("secret=<redacted>", aioclient_span.data.http.params)
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

        assert("http.X-Capture-This" in tornado_span.data.custom.tags)
        self.assertEqual('this', tornado_span.data.custom.tags['http.X-Capture-This'])
        assert("http.X-Capture-That" in tornado_span.data.custom.tags)
        self.assertEqual('that', tornado_span.data.custom.tags['http.X-Capture-That'])
