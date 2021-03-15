# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import aiohttp
import asyncio
import unittest

from instana.singletons import async_tracer, agent

import tests.apps.flask_app
import tests.apps.aiohttp_app
from ..helpers import testenv


class TestAiohttp(unittest.TestCase):

    async def fetch(self, session, url, headers=None):
        try:
            async with session.get(url, headers=headers) as response:
                return response
        except aiohttp.web_exceptions.HTTPException:
            pass

    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = async_tracer.recorder
        self.recorder.clear_spans()

        # New event loop for every test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        pass

    def test_client_get(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["wsgi_server"] + "/")

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
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(wsgi_span.ec)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["wsgi_server"] + "/",
                         aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_client_get_301(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["wsgi_server"] + "/301")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        wsgi_span1 = spans[0]
        wsgi_span2 = spans[1]
        aiohttp_span = spans[2]
        test_span = spans[3]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)
        self.assertEqual(traceId, wsgi_span1.t)
        self.assertEqual(traceId, wsgi_span2.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)
        self.assertEqual(wsgi_span1.p, aiohttp_span.s)
        self.assertEqual(wsgi_span2.p, aiohttp_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(wsgi_span1.ec)
        self.assertIsNone(wsgi_span2.ec)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["wsgi_server"] + "/301",
                         aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], wsgi_span2.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_client_get_405(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["wsgi_server"] + "/405")

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
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(wsgi_span.ec)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(405, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["wsgi_server"] + "/405",
                         aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_client_get_500(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["wsgi_server"] + "/500")

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
        self.assertIsNone(test_span.ec)
        self.assertEqual(aiohttp_span.ec, 1)
        self.assertEqual(wsgi_span.ec, 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(500, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["wsgi_server"] + "/500",
                         aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertEqual('INTERNAL SERVER ERROR',
                         aiohttp_span.data["http"]["error"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_client_get_504(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["wsgi_server"] + "/504")

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
        self.assertIsNone(test_span.ec)
        self.assertEqual(aiohttp_span.ec, 1)
        self.assertEqual(wsgi_span.ec, 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(504, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["wsgi_server"] + "/504",
                         aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertEqual('GATEWAY TIMEOUT', aiohttp_span.data["http"]["error"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_client_get_with_params_to_scrub(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["wsgi_server"] + "/?secret=yeah")

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
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(wsgi_span.ec)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["wsgi_server"] + "/",
                         aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertEqual("secret=<redacted>",
                         aiohttp_span.data["http"]["params"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_client_response_header_capture(self):
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ['X-Capture-This']

        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["wsgi_server"] + "/response_headers")

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
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aiohttp_span.ec)
        self.assertIsNone(wsgi_span.ec)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data["http"]["status"])
        self.assertEqual(testenv["wsgi_server"] + "/response_headers", aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert "X-Capture-This" in aiohttp_span.data["http"]["header"]
        self.assertEqual("Ok", aiohttp_span.data["http"]["header"]["X-Capture-This"])

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], wsgi_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

        agent.options.extra_http_headers = original_extra_http_headers

    def test_client_error(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, 'http://doesnotexist:10/')

        response = None
        try:
            response = self.loop.run_until_complete(test())
        except:
            pass

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        aiohttp_span = spans[0]
        test_span = spans[1]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aiohttp_span.t)

        # Parent relationships
        self.assertEqual(aiohttp_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(aiohttp_span.ec, 1)

        self.assertEqual("aiohttp-client", aiohttp_span.n)
        self.assertIsNone(aiohttp_span.data["http"]["status"])
        self.assertEqual("http://doesnotexist:10/",
                         aiohttp_span.data["http"]["url"])
        self.assertEqual("GET", aiohttp_span.data["http"]["method"])
        self.assertIsNotNone(aiohttp_span.data["http"]["error"])
        assert(len(aiohttp_span.data["http"]["error"]))
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertIsNone(response)
