# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import aiohttp
import asyncio
import unittest

import tests.apps.aiohttp_app
from ..helpers import testenv

from instana.singletons import async_tracer, agent


class TestAiohttpServer(unittest.TestCase):

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

    def test_server_get(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aioclient_span.t)
        self.assertEqual(traceId, aioserver_span.t)

        # Parent relationships
        self.assertEqual(aioclient_span.p, test_span.s)
        self.assertEqual(aioserver_span.p, aioclient_span.s)

        # Synthetic
        self.assertIsNone(test_span.sy)
        self.assertIsNone(aioclient_span.sy)
        self.assertIsNone(aioserver_span.sy)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aioclient_span.ec)
        self.assertIsNone(aioserver_span.ec)

        self.assertEqual("aiohttp-server", aioserver_span.n)
        self.assertEqual(200, aioserver_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/", aioserver_span.data["http"]["url"])
        self.assertEqual("GET", aioserver_span.data["http"]["method"])
        self.assertIsNone(aioserver_span.stack)

        self.assertEqual("aiohttp-client", aioclient_span.n)
        self.assertEqual(200, aioclient_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/", aioclient_span.data["http"]["url"])
        self.assertEqual("GET", aioclient_span.data["http"]["method"])
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_server_get_204(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/204")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        trace_id = test_span.t
        self.assertEqual(trace_id, aioclient_span.t)
        self.assertEqual(trace_id, aioserver_span.t)

        # Parent relationships
        self.assertEqual(aioclient_span.p, test_span.s)
        self.assertEqual(aioserver_span.p, aioclient_span.s)

        # Synthetic
        self.assertIsNone(test_span.sy)
        self.assertIsNone(aioclient_span.sy)
        self.assertIsNone(aioserver_span.sy)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aioclient_span.ec)
        self.assertIsNone(aioserver_span.ec)

        self.assertEqual("aiohttp-server", aioserver_span.n)
        self.assertEqual(204, aioserver_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/204", aioserver_span.data["http"]["url"])
        self.assertEqual("GET", aioserver_span.data["http"]["method"])
        self.assertIsNone(aioserver_span.stack)

        self.assertEqual("aiohttp-client", aioclient_span.n)
        self.assertEqual(204, aioclient_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/204", aioclient_span.data["http"]["url"])
        self.assertEqual("GET", aioclient_span.data["http"]["method"])
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(isinstance(aioclient_span.stack, list))
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], trace_id)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % trace_id)

    def test_server_synthetic_request(self):
        async def test():
            headers = {
                'X-INSTANA-SYNTHETIC': '1'
            }

            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/", headers=headers)

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertTrue(aioserver_span.sy)
        self.assertIsNone(aioclient_span.sy)
        self.assertIsNone(test_span.sy)

    def test_server_get_with_params_to_scrub(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/?secret=iloveyou")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aioclient_span.t)
        self.assertEqual(traceId, aioserver_span.t)

        # Parent relationships
        self.assertEqual(aioclient_span.p, test_span.s)
        self.assertEqual(aioserver_span.p, aioclient_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aioclient_span.ec)
        self.assertIsNone(aioserver_span.ec)

        self.assertEqual("aiohttp-server", aioserver_span.n)
        self.assertEqual(200, aioserver_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/", aioserver_span.data["http"]["url"])
        self.assertEqual("GET", aioserver_span.data["http"]["method"])
        self.assertEqual("secret=<redacted>",
                         aioserver_span.data["http"]["params"])
        self.assertIsNone(aioserver_span.stack)

        self.assertEqual("aiohttp-client", aioclient_span.n)
        self.assertEqual(200, aioclient_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/", aioclient_span.data["http"]["url"])
        self.assertEqual("GET", aioclient_span.data["http"]["method"])
        self.assertEqual("secret=<redacted>",
                         aioclient_span.data["http"]["params"])
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_server_custom_header_capture(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    # Hack together a manual custom headers list
                    agent.options.extra_http_headers = [
                        u'X-Capture-This', u'X-Capture-That']

                    headers = dict()
                    headers['X-Capture-This'] = 'this'
                    headers['X-Capture-That'] = 'that'

                    return await self.fetch(session, testenv["aiohttp_server"] + "/?secret=iloveyou", headers=headers)

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aioclient_span.t)
        self.assertEqual(traceId, aioserver_span.t)

        # Parent relationships
        self.assertEqual(aioclient_span.p, test_span.s)
        self.assertEqual(aioserver_span.p, aioclient_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aioclient_span.ec)
        self.assertIsNone(aioserver_span.ec)

        self.assertEqual("aiohttp-server", aioserver_span.n)
        self.assertEqual(200, aioserver_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/", aioserver_span.data["http"]["url"])
        self.assertEqual("GET", aioserver_span.data["http"]["method"])
        self.assertEqual("secret=<redacted>",
                         aioserver_span.data["http"]["params"])
        self.assertIsNone(aioserver_span.stack)

        self.assertEqual("aiohttp-client", aioclient_span.n)
        self.assertEqual(200, aioclient_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/", aioclient_span.data["http"]["url"])
        self.assertEqual("GET", aioclient_span.data["http"]["method"])
        self.assertEqual("secret=<redacted>",
                         aioclient_span.data["http"]["params"])
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

        assert "X-Capture-This" in aioserver_span.data["http"]["header"]
        self.assertEqual("this", aioserver_span.data["http"]["header"]["X-Capture-This"])
        assert "X-Capture-That" in aioserver_span.data["http"]["header"]
        self.assertEqual("that", aioserver_span.data["http"]["header"]["X-Capture-That"])

    def test_server_get_401(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/401")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aioclient_span.t)
        self.assertEqual(traceId, aioserver_span.t)

        # Parent relationships
        self.assertEqual(aioclient_span.p, test_span.s)
        self.assertEqual(aioserver_span.p, aioclient_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(aioclient_span.ec)
        self.assertIsNone(aioserver_span.ec)

        self.assertEqual("aiohttp-server", aioserver_span.n)
        self.assertEqual(401, aioserver_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/401", aioserver_span.data["http"]["url"])
        self.assertEqual("GET", aioserver_span.data["http"]["method"])
        self.assertIsNone(aioserver_span.stack)

        self.assertEqual("aiohttp-client", aioclient_span.n)
        self.assertEqual(401, aioclient_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/401", aioclient_span.data["http"]["url"])
        self.assertEqual("GET", aioclient_span.data["http"]["method"])
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_server_get_500(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/500")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aioclient_span.t)
        self.assertEqual(traceId, aioserver_span.t)

        # Parent relationships
        self.assertEqual(aioclient_span.p, test_span.s)
        self.assertEqual(aioserver_span.p, aioclient_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(aioclient_span.ec, 1)
        self.assertEqual(aioserver_span.ec, 1)

        self.assertEqual("aiohttp-server", aioserver_span.n)
        self.assertEqual(500, aioserver_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/500", aioserver_span.data["http"]["url"])
        self.assertEqual("GET", aioserver_span.data["http"]["method"])
        self.assertIsNone(aioserver_span.stack)

        self.assertEqual("aiohttp-client", aioclient_span.n)
        self.assertEqual(500, aioclient_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/500", aioclient_span.data["http"]["url"])
        self.assertEqual("GET", aioclient_span.data["http"]["method"])
        self.assertEqual('I must simulate errors.',
                         aioclient_span.data["http"]["error"])
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert "X-INSTANA-T" in response.headers
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert "X-INSTANA-S" in response.headers
        self.assertEqual(response.headers["X-INSTANA-S"], aioserver_span.s)
        assert "X-INSTANA-L" in response.headers
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert "Server-Timing" in response.headers
        self.assertEqual(
            response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_server_get_exception(self):
        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, testenv["aiohttp_server"] + "/exception")

        response = self.loop.run_until_complete(test())

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        aioserver_span = spans[0]
        aioclient_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(async_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, aioclient_span.t)
        self.assertEqual(traceId, aioserver_span.t)

        # Parent relationships
        self.assertEqual(aioclient_span.p, test_span.s)
        self.assertEqual(aioserver_span.p, aioclient_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(aioclient_span.ec, 1)
        self.assertEqual(aioserver_span.ec, 1)

        self.assertEqual("aiohttp-server", aioserver_span.n)
        self.assertEqual(500, aioserver_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/exception", aioserver_span.data["http"]["url"])
        self.assertEqual("GET", aioserver_span.data["http"]["method"])
        self.assertIsNone(aioserver_span.stack)

        self.assertEqual("aiohttp-client", aioclient_span.n)
        self.assertEqual(500, aioclient_span.data["http"]["status"])
        self.assertEqual(testenv["aiohttp_server"] +
                         "/exception", aioclient_span.data["http"]["url"])
        self.assertEqual("GET", aioclient_span.data["http"]["method"])
        self.assertEqual('Internal Server Error',
                         aioclient_span.data["http"]["error"])
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)
