from __future__ import absolute_import

import time
import asyncio
import aiohttp
import unittest

import tornado
from tornado.httpclient import AsyncHTTPClient

import tests.apps.tornado_server

from instana.singletons import async_tracer, agent
from ..helpers import testenv, get_first_span_by_name, get_first_span_by_filter


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

        # New event loop for every test
        # self.loop = tornado.ioloop.IOLoop.current()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.http_client = AsyncHTTPClient()

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

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertIsNotNone(tornado_span)
        self.assertIsNotNone(aiohttp_span)
        self.assertIsNotNone(test_span)

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Synthetic
        self.assertIsNone(tornado_span.sy)
        self.assertIsNone(aiohttp_span.sy)
        self.assertIsNone(test_span.sy)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual(200, tornado_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", tornado_span.data["http"]["url"])
        self.assertIsNone(tornado_span.data["http"]["params"])
        self.assertEqual("GET", tornado_span.data["http"]["method"])
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertTrue("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        self.assertTrue("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        self.assertTrue("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        self.assertTrue("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_post(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.post(session, testenv["tornado_server"] + "/")

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        
        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertIsNotNone(tornado_span)
        self.assertIsNotNone(aiohttp_span)
        self.assertIsNotNone(test_span)

        self.assertIsNone(async_tracer.active_span)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual("sdk", test_span.n)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual(200, tornado_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", tornado_span.data["http"]["url"])
        self.assertIsNone(tornado_span.data["http"]["params"])
        self.assertEqual("POST", tornado_span.data["http"]["method"])
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", aiohttp_span.data["http"]["url"])
        self.assertEqual("POST", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertTrue("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        self.assertTrue("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        self.assertTrue("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        self.assertTrue("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_synthetic_request(self):
        async def test():
            headers = {
                'X-Instana-Synthetic': '1'
            }
            
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/", headers=headers)

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertTrue(tornado_span.sy)
        self.assertIsNone(aiohttp_span.sy)
        self.assertIsNone(test_span.sy)

    def test_get_301(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/301")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        filter = lambda span: span.n == "tornado-server" and span.data["http"]["status"] == 301
        tornado_301_span = get_first_span_by_filter(spans, filter)
        filter = lambda span: span.n == "tornado-server" and span.data["http"]["status"] == 200
        tornado_span = get_first_span_by_filter(spans, filter)
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertIsNotNone(tornado_301_span)
        self.assertIsNotNone(tornado_span)
        self.assertIsNotNone(aiohttp_span)
        self.assertIsNotNone(test_span)

        self.assertIsNone(async_tracer.active_span)

        self.assertEqual("tornado-server", tornado_301_span.n)
        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual("sdk", test_span.n)

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
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(tornado_301_span.ec)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual(301, tornado_301_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/301", tornado_301_span.data["http"]["url"])
        self.assertIsNone(tornado_span.data["http"]["params"])
        self.assertEqual("GET", tornado_301_span.data["http"]["method"])
        self.assertIsNotNone(tornado_301_span.stack)
        self.assertTrue(type(tornado_301_span.stack) is list)
        self.assertTrue(len(tornado_301_span.stack) > 1)

        self.assertEqual(200, tornado_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", tornado_span.data["http"]["url"])
        self.assertEqual("GET", tornado_span.data["http"]["method"])
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/301", aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertTrue("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        self.assertTrue("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        self.assertTrue("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        self.assertTrue("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_405(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/405")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertIsNotNone(tornado_span)
        self.assertIsNotNone(aiohttp_span)
        self.assertIsNotNone(test_span)

        self.assertIsNone(async_tracer.active_span)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual("sdk", test_span.n)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual(405, tornado_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/405", tornado_span.data["http"]["url"])
        self.assertIsNone(tornado_span.data["http"]["params"])
        self.assertEqual("GET", tornado_span.data["http"]["method"])
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual(405, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/405", aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertTrue("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        self.assertTrue("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        self.assertTrue("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        self.assertTrue("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_500(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/500")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertIsNotNone(tornado_span)
        self.assertIsNotNone(aiohttp_span)
        self.assertIsNotNone(test_span)

        self.assertIsNone(async_tracer.active_span)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual("sdk", test_span.n)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(aiohttp_span.ec, 1)
        self.assertEqual(tornado_span.ec, 1)

        self.assertEqual(500, tornado_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/500", tornado_span.data["http"]["url"])
        self.assertIsNone(tornado_span.data["http"]["params"])
        self.assertEqual("GET", tornado_span.data["http"]["method"])
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual(500, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/500", aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertEqual('Internal Server Error', aiohttp_span.data["http"]["error"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertTrue("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        self.assertTrue("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        self.assertTrue("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        self.assertTrue("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_504(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/504")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertIsNotNone(tornado_span)
        self.assertIsNotNone(aiohttp_span)
        self.assertIsNotNone(test_span)

        self.assertIsNone(async_tracer.active_span)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual("sdk", test_span.n)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(aiohttp_span.ec, 1)
        self.assertEqual(tornado_span.ec, 1)

        self.assertEqual(504, tornado_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/504", tornado_span.data["http"]["url"])
        self.assertIsNone(tornado_span.data["http"]["params"])
        self.assertEqual("GET", tornado_span.data["http"]["method"])
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual(504, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/504", aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertEqual('Gateway Timeout', aiohttp_span.data["http"]["error"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertTrue("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        self.assertTrue("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        self.assertTrue("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        self.assertTrue("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_with_params_to_scrub(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["tornado_server"] + "/?secret=yeah")

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        self.assertIsNone(async_tracer.active_span)

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertIsNotNone(tornado_span)
        self.assertIsNotNone(aiohttp_span)
        self.assertIsNotNone(test_span)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual("sdk", test_span.n)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual(200, tornado_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", tornado_span.data["http"]["url"])
        self.assertEqual("secret=<redacted>", tornado_span.data["http"]["params"])
        self.assertEqual("GET", tornado_span.data["http"]["method"])
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertEqual("secret=<redacted>", aiohttp_span.data["http"]["params"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertTrue("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        self.assertTrue("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        self.assertTrue("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        self.assertTrue("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_custom_header_capture(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    # Hack together a manual custom headers list
                    agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

                    headers = dict()
                    headers['X-Capture-This'] = 'this'
                    headers['X-Capture-That'] = 'that'

                    return await self.fetch(session, testenv["tornado_server"] + "/?secret=iloveyou", headers=headers)

        response = tornado.ioloop.IOLoop.current().run_sync(test)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        tornado_span = get_first_span_by_name(spans, "tornado-server")
        aiohttp_span = get_first_span_by_name(spans, "aiohttp-client")
        test_span = get_first_span_by_name(spans, "sdk")

        self.assertIsNotNone(tornado_span)
        self.assertIsNotNone(aiohttp_span)
        self.assertIsNotNone(test_span)

        self.assertIsNone(async_tracer.active_span)

        self.assertEqual("tornado-server", tornado_span.n)
        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual("sdk", test_span.n)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, tornado_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(tornado_span.p, aiohttp_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(tornado_span.ec)

        self.assertEqual(200, tornado_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", tornado_span.data["http"]["url"])
        self.assertEqual("secret=<redacted>", tornado_span.data["http"]["params"])
        self.assertEqual("GET", tornado_span.data["http"]["method"])
        self.assertIsNotNone(tornado_span.stack)
        self.assertTrue(type(tornado_span.stack) is list)
        self.assertTrue(len(tornado_span.stack) > 1)

        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertEqual("secret=<redacted>", aiohttp_span.data["http"]["params"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertTrue("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        self.assertTrue("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], tornado_span.s)
        self.assertTrue("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        self.assertTrue("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

        self.assertTrue("http.X-Capture-This" in tornado_span.data["custom"]["tags"])
        self.assertEqual('this', tornado_span.data["custom"]["tags"]['http.X-Capture-This'])
        self.assertTrue("http.X-Capture-That" in tornado_span.data["custom"]["tags"])
        self.assertEqual('that', tornado_span.data["custom"]["tags"]['http.X-Capture-That'])
