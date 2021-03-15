# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import time
import asyncio
import unittest

import tornado
from tornado.httpclient import AsyncHTTPClient
from instana.singletons import tornado_tracer

import tests.apps.tornado_server
from ..helpers import testenv

from nose.plugins.skip import SkipTest
raise SkipTest("Non deterministic tests TBR")

class TestTornadoClient(unittest.TestCase):

    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tornado_tracer.recorder
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
            with tornado_tracer.start_active_span('test'):
                return await self.http_client.fetch(testenv["tornado_server"] + "/")

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))

        server_span = spans[0]
        client_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(tornado_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, client_span.t)
        self.assertEqual(traceId, server_span.t)

        # Parent relationships
        self.assertEqual(client_span.p, test_span.s)
        self.assertEqual(server_span.p, client_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        self.assertEqual("tornado-server", server_span.n)
        self.assertEqual(200, server_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", server_span.data["http"]["url"])
        self.assertIsNone(server_span.data["http"]["params"])
        self.assertEqual("GET", server_span.data["http"]["method"])
        self.assertIsNotNone(server_span.stack)
        self.assertTrue(type(server_span.stack) is list)
        self.assertTrue(len(server_span.stack) > 1)

        self.assertEqual("tornado-client", client_span.n)
        self.assertEqual(200, client_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", client_span.data["http"]["url"])
        self.assertEqual("GET", client_span.data["http"]["method"])
        self.assertIsNotNone(client_span.stack)
        self.assertTrue(type(client_span.stack) is list)
        self.assertTrue(len(client_span.stack) > 1)

        assert("X-INSTANA-T" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert("X-INSTANA-S" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-S"], server_span.s)
        assert("X-INSTANA-L" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_post(self):
        async def test():
            with tornado_tracer.start_active_span('test'):
                return await self.http_client.fetch(testenv["tornado_server"] + "/", method="POST", body='asdf')

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = spans[0]
        client_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(tornado_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, client_span.t)
        self.assertEqual(traceId, server_span.t)

        # Parent relationships
        self.assertEqual(client_span.p, test_span.s)
        self.assertEqual(server_span.p, client_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        self.assertEqual("tornado-server", server_span.n)
        self.assertEqual(200, server_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", server_span.data["http"]["url"])
        self.assertIsNone(server_span.data["http"]["params"])
        self.assertEqual("POST", server_span.data["http"]["method"])
        self.assertIsNotNone(server_span.stack)
        self.assertTrue(type(server_span.stack) is list)
        self.assertTrue(len(server_span.stack) > 1)

        self.assertEqual("tornado-client", client_span.n)
        self.assertEqual(200, client_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", client_span.data["http"]["url"])
        self.assertEqual("POST", client_span.data["http"]["method"])
        self.assertIsNotNone(client_span.stack)
        self.assertTrue(type(client_span.stack) is list)
        self.assertTrue(len(client_span.stack) > 1)

        assert("X-INSTANA-T" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert("X-INSTANA-S" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-S"], server_span.s)
        assert("X-INSTANA-L" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_301(self):
        async def test():
            with tornado_tracer.start_active_span('test'):
                return await self.http_client.fetch(testenv["tornado_server"] + "/301")

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        server301_span = spans[0]
        server_span = spans[1]
        client_span = spans[2]
        test_span = spans[3]

        self.assertIsNone(tornado_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, client_span.t)
        self.assertEqual(traceId, server301_span.t)
        self.assertEqual(traceId, server_span.t)

        # Parent relationships
        self.assertEqual(server301_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)
        self.assertEqual(server_span.p, client_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        self.assertEqual("tornado-server", server_span.n)
        self.assertEqual(200, server_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", server_span.data["http"]["url"])
        self.assertIsNone(server_span.data["http"]["params"])
        self.assertEqual("GET", server_span.data["http"]["method"])
        self.assertIsNotNone(server_span.stack)
        self.assertTrue(type(server_span.stack) is list)
        self.assertTrue(len(server_span.stack) > 1)

        self.assertEqual("tornado-server", server301_span.n)
        self.assertEqual(301, server301_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/301", server301_span.data["http"]["url"])
        self.assertIsNone(server301_span.data["http"]["params"])
        self.assertEqual("GET", server301_span.data["http"]["method"])
        self.assertIsNotNone(server301_span.stack)
        self.assertTrue(type(server301_span.stack) is list)
        self.assertTrue(len(server301_span.stack) > 1)

        self.assertEqual("tornado-client", client_span.n)
        self.assertEqual(200, client_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/301", client_span.data["http"]["url"])
        self.assertEqual("GET", client_span.data["http"]["method"])
        self.assertIsNotNone(client_span.stack)
        self.assertTrue(type(client_span.stack) is list)
        self.assertTrue(len(client_span.stack) > 1)

        assert("X-INSTANA-T" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert("X-INSTANA-S" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-S"], server_span.s)
        assert("X-INSTANA-L" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_405(self):
        async def test():
            with tornado_tracer.start_active_span('test'):
                try:
                    return await self.http_client.fetch(testenv["tornado_server"] + "/405")
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = spans[0]
        client_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(tornado_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, client_span.t)
        self.assertEqual(traceId, server_span.t)

        # Parent relationships
        self.assertEqual(client_span.p, test_span.s)
        self.assertEqual(server_span.p, client_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(client_span.ec, 1)
        self.assertIsNone(server_span.ec)

        self.assertEqual("tornado-server", server_span.n)
        self.assertEqual(405, server_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/405", server_span.data["http"]["url"])
        self.assertIsNone(server_span.data["http"]["params"])
        self.assertEqual("GET", server_span.data["http"]["method"])
        self.assertIsNotNone(server_span.stack)
        self.assertTrue(type(server_span.stack) is list)
        self.assertTrue(len(server_span.stack) > 1)

        self.assertEqual("tornado-client", client_span.n)
        self.assertEqual(405, client_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/405", client_span.data["http"]["url"])
        self.assertEqual("GET", client_span.data["http"]["method"])
        self.assertIsNotNone(client_span.stack)
        self.assertTrue(type(client_span.stack) is list)
        self.assertTrue(len(client_span.stack) > 1)

        assert("X-INSTANA-T" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert("X-INSTANA-S" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-S"], server_span.s)
        assert("X-INSTANA-L" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_500(self):
        async def test():
            with tornado_tracer.start_active_span('test'):
                try:
                    return await self.http_client.fetch(testenv["tornado_server"] + "/500")
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = spans[0]
        client_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(tornado_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, client_span.t)
        self.assertEqual(traceId, server_span.t)

        # Parent relationships
        self.assertEqual(client_span.p, test_span.s)
        self.assertEqual(server_span.p, client_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(client_span.ec, 1)
        self.assertEqual(server_span.ec, 1)

        self.assertEqual("tornado-server", server_span.n)
        self.assertEqual(500, server_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/500", server_span.data["http"]["url"])
        self.assertIsNone(server_span.data["http"]["params"])
        self.assertEqual("GET", server_span.data["http"]["method"])
        self.assertIsNotNone(server_span.stack)
        self.assertTrue(type(server_span.stack) is list)
        self.assertTrue(len(server_span.stack) > 1)

        self.assertEqual("tornado-client", client_span.n)
        self.assertEqual(500, client_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/500", client_span.data["http"]["url"])
        self.assertEqual("GET", client_span.data["http"]["method"])
        self.assertIsNotNone(client_span.stack)
        self.assertTrue(type(client_span.stack) is list)
        self.assertTrue(len(client_span.stack) > 1)

        assert("X-INSTANA-T" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert("X-INSTANA-S" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-S"], server_span.s)
        assert("X-INSTANA-L" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_504(self):
        async def test():
            with tornado_tracer.start_active_span('test'):
                try:
                    return await self.http_client.fetch(testenv["tornado_server"] + "/504")
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = spans[0]
        client_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(tornado_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, client_span.t)
        self.assertEqual(traceId, server_span.t)

        # Parent relationships
        self.assertEqual(client_span.p, test_span.s)
        self.assertEqual(server_span.p, client_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(client_span.ec, 1)
        self.assertEqual(server_span.ec, 1)

        self.assertEqual("tornado-server", server_span.n)
        self.assertEqual(504, server_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/504", server_span.data["http"]["url"])
        self.assertIsNone(server_span.data["http"]["params"])
        self.assertEqual("GET", server_span.data["http"]["method"])
        self.assertIsNotNone(server_span.stack)
        self.assertTrue(type(server_span.stack) is list)
        self.assertTrue(len(server_span.stack) > 1)

        self.assertEqual("tornado-client", client_span.n)
        self.assertEqual(504, client_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/504", client_span.data["http"]["url"])
        self.assertEqual("GET", client_span.data["http"]["method"])
        self.assertIsNotNone(client_span.stack)
        self.assertTrue(type(client_span.stack) is list)
        self.assertTrue(len(client_span.stack) > 1)

        assert("X-INSTANA-T" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert("X-INSTANA-S" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-S"], server_span.s)
        assert("X-INSTANA-L" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)

    def test_get_with_params_to_scrub(self):
        async def test():
            with tornado_tracer.start_active_span('test'):
                return await self.http_client.fetch(testenv["tornado_server"] + "/?secret=yeah")

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = spans[0]
        client_span = spans[1]
        test_span = spans[2]

        self.assertIsNone(tornado_tracer.active_span)

        # Same traceId
        traceId = test_span.t
        self.assertEqual(traceId, client_span.t)
        self.assertEqual(traceId, server_span.t)

        # Parent relationships
        self.assertEqual(client_span.p, test_span.s)
        self.assertEqual(server_span.p, client_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        self.assertEqual("tornado-server", server_span.n)
        self.assertEqual(200, server_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", server_span.data["http"]["url"])
        self.assertEqual('secret=<redacted>', server_span.data["http"]["params"])
        self.assertEqual("GET", server_span.data["http"]["method"])
        self.assertIsNotNone(server_span.stack)
        self.assertTrue(type(server_span.stack) is list)
        self.assertTrue(len(server_span.stack) > 1)

        self.assertEqual("tornado-client", client_span.n)
        self.assertEqual(200, client_span.data["http"]["status"])
        self.assertEqual(testenv["tornado_server"] + "/", client_span.data["http"]["url"])
        self.assertEqual('secret=<redacted>', client_span.data["http"]["params"])
        self.assertEqual("GET", client_span.data["http"]["method"])
        self.assertIsNotNone(client_span.stack)
        self.assertTrue(type(client_span.stack) is list)
        self.assertTrue(len(client_span.stack) > 1)

        assert("X-INSTANA-T" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-T"], traceId)
        assert("X-INSTANA-S" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-S"], server_span.s)
        assert("X-INSTANA-L" in response.headers)
        self.assertEqual(response.headers["X-INSTANA-L"], '1')
        assert("Server-Timing" in response.headers)
        self.assertEqual(response.headers["Server-Timing"], "intid;desc=%s" % traceId)
