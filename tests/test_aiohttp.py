from __future__ import absolute_import

import aiohttp
import asyncio
import unittest

from instana.singletons import async_tracer, agent

from .helpers import testenv


class TestAiohttp(unittest.TestCase):
    async def fetch(self, session, url, headers=None):
        async with session.get(url, headers=headers) as response:
            return response

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
        response = None

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

    def test_client_get_301(self):
        response = None

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
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aiohttp_span.error)
        self.assertIsNone(aiohttp_span.ec)
        self.assertFalse(wsgi_span1.error)
        self.assertIsNone(wsgi_span1.ec)
        self.assertFalse(wsgi_span2.error)
        self.assertIsNone(wsgi_span2.ec)

        self.assertEqual("aiohttp", aiohttp_span.n)
        self.assertEqual(200, aiohttp_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5000/301", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], wsgi_span2.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_client_get_500(self):
        response = None

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

    def test_client_get_504(self):
        response = None

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

    def test_client_get_with_params_to_scrub(self):
        response = None

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
        self.assertEqual("secret=<redacted>", aiohttp_span.data.http.params)
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

    def test_client_error(self):
        response = None

        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    return await self.fetch(session, 'http://doesnotexist:10/')

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
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertTrue(aiohttp_span.error)
        self.assertEqual(aiohttp_span.ec, 1)

        self.assertEqual("aiohttp", aiohttp_span.n)
        self.assertIsNone(aiohttp_span.data.http.status)
        self.assertEqual("http://doesnotexist:10/", aiohttp_span.data.http.url)
        self.assertEqual("GET", aiohttp_span.data.http.method)
        self.assertEqual('Cannot connect to host doesnotexist:10 ssl:None [nodename nor servname provided, or not known]', aiohttp_span.data.http.error)
        self.assertIsNotNone(aiohttp_span.stack)
        self.assertTrue(type(aiohttp_span.stack) is list)
        self.assertTrue(len(aiohttp_span.stack) > 1)

        self.assertIsNone(response)

    def test_server_get(self):
        response = None

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

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aioclient_span.error)
        self.assertIsNone(aioclient_span.ec)
        self.assertFalse(aioserver_span.error)
        self.assertIsNone(aioserver_span.ec)

        self.assertEqual("aiohttp", aioclient_span.n)
        self.assertEqual(200, aioclient_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5002/", aioclient_span.data.http.url)
        self.assertEqual("GET", aioclient_span.data.http.method)
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], aioserver_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_server_get_with_params_to_scrub(self):
        response = None

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
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aioclient_span.error)
        self.assertIsNone(aioclient_span.ec)
        self.assertFalse(aioserver_span.error)
        self.assertIsNone(aioserver_span.ec)

        self.assertEqual("aiohttp", aioclient_span.n)
        self.assertEqual(200, aioclient_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5002/", aioclient_span.data.http.url)
        self.assertEqual("GET", aioclient_span.data.http.method)
        self.assertEqual("secret=<redacted>", aioclient_span.data.http.params)
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], aioserver_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)


    def test_server_custom_header_capture(self):
        response = None

        async def test():
            with async_tracer.start_active_span('test'):
                async with aiohttp.ClientSession() as session:
                    # Hack together a manual custom headers list
                    agent.extra_headers = [u'X-Capture-This', u'X-Capture-That']

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
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(aioclient_span.error)
        self.assertIsNone(aioclient_span.ec)
        self.assertFalse(aioserver_span.error)
        self.assertIsNone(aioserver_span.ec)

        self.assertEqual("aiohttp", aioclient_span.n)
        self.assertEqual(200, aioclient_span.data.http.status)
        self.assertEqual("http://127.0.0.1:5002/", aioclient_span.data.http.url)
        self.assertEqual("GET", aioclient_span.data.http.method)
        self.assertEqual("secret=<redacted>", aioclient_span.data.http.params)
        self.assertIsNotNone(aioclient_span.stack)
        self.assertTrue(type(aioclient_span.stack) is list)
        self.assertTrue(len(aioclient_span.stack) > 1)

        assert("X-Instana-T" in response.headers)
        self.assertEqual(response.headers["X-Instana-T"], traceId)
        assert("X-Instana-S" in response.headers)
        self.assertEqual(response.headers["X-Instana-S"], aioserver_span.s)
        assert("X-Instana-L" in response.headers)
        self.assertEqual(response.headers["X-Instana-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

        assert("http.X-Capture-This" in aioserver_span.data.custom.tags)
        self.assertEqual('this', aioserver_span.data.custom.tags['http.X-Capture-This'])
        assert("http.X-Capture-That" in aioserver_span.data.custom.tags)
        self.assertEqual('that', aioserver_span.data.custom.tags['http.X-Capture-That'])



