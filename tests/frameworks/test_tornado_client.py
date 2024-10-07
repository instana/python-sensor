# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
import asyncio
import pytest
from typing import Generator

import tornado
from tornado.httpclient import AsyncHTTPClient
from instana.singletons import tracer
from instana.span.span import get_current_span

from instana.util.ids import hex_id
import tests.apps.tornado_server
from tests.helpers import testenv, get_first_span_by_name, get_first_span_by_filter

class TestTornadoClient:

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """ Clear all spans before a test run """
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

        # New event loop for every test
        # self.loop = tornado.ioloop.IOLoop.current()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.http_client = AsyncHTTPClient()
        yield
        self.http_client.close()

    def test_get(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                return await self.http_client.fetch(testenv["tornado_server"] + "/")

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "tornado-server")
        client_span = get_first_span_by_name(spans, "tornado-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        assert server_span.n == "tornado-server"
        assert server_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == server_span.data["http"]["url"]
        assert not server_span.data["http"]["params"]
        assert server_span.data["http"]["method"] == "GET"
        # assert server_span.stack
        # assert type(server_span.stack) is list
        # assert len(server_span.stack) > 1

        assert client_span.n == "tornado-client"
        assert client_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == client_span.data["http"]["url"]
        assert client_span.data["http"]["method"] == "GET"
        assert client_span.stack
        assert type(client_span.stack) is list
        assert len(client_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(server_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_post(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                return await self.http_client.fetch(testenv["tornado_server"] + "/", method="POST", body='asdf')

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "tornado-server")
        client_span = get_first_span_by_name(spans, "tornado-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        assert server_span.n == "tornado-server"
        assert server_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == server_span.data["http"]["url"]
        assert not server_span.data["http"]["params"]
        assert server_span.data["http"]["method"] == "POST"

        assert client_span.n == "tornado-client"
        assert client_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == client_span.data["http"]["url"]
        assert client_span.data["http"]["method"] == "POST"
        assert client_span.stack
        assert type(client_span.stack) is list
        assert len(client_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(server_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_get_301(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                return await self.http_client.fetch(testenv["tornado_server"] + "/301")

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 5

        server301_span = spans[0]
        server_span = spans[1]
        client_span = spans[2]
        client301_span = spans[3]
        test_span = spans[4]

        filter = lambda span: span.n == "tornado-server" and span.data["http"]["status"] == 301
        server301_span = get_first_span_by_filter(spans, filter)
        filter = lambda span: span.n == "tornado-server" and span.data["http"]["status"] == 200
        server_span = get_first_span_by_filter(spans, filter)
        filter = lambda span: span.n == "tornado-client" and span.data["http"]["url"] == testenv["tornado_server"] + "/"
        client_span = get_first_span_by_filter(spans, filter)
        filter = lambda span: span.n == "tornado-client" and span.data["http"]["url"] == testenv["tornado_server"] + "/301"
        client301_span = get_first_span_by_filter(spans, filter)
        test_span = get_first_span_by_name(spans, "sdk")

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == client301_span.t
        assert traceId == server301_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert server301_span.p == client301_span.s
        assert client_span.p == test_span.s
        assert client301_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        assert server_span.n == "tornado-server"
        assert server_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == server_span.data["http"]["url"]
        assert not server_span.data["http"]["params"]
        assert server_span.data["http"]["method"] == "GET"

        assert server301_span.n == "tornado-server"
        assert server301_span.data["http"]["status"] == 301
        assert testenv["tornado_server"] + "/301" == server301_span.data["http"]["url"]
        assert not server301_span.data["http"]["params"]
        assert server301_span.data["http"]["method"] == "GET"

        assert client_span.n == "tornado-client"
        assert client_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == client_span.data["http"]["url"]
        assert client_span.data["http"]["method"] == "GET"
        assert client_span.stack
        assert type(client_span.stack) is list
        assert len(client_span.stack) > 1

        assert client301_span.n == "tornado-client"
        assert client301_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/301" == client301_span.data["http"]["url"]
        assert client301_span.data["http"]["method"] == "GET"
        assert client301_span.stack
        assert type(client301_span.stack) is list
        assert len(client301_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(server_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_get_405(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                try:
                    return await self.http_client.fetch(testenv["tornado_server"] + "/405")
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "tornado-server")
        client_span = get_first_span_by_name(spans, "tornado-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert client_span.ec == 1
        assert not server_span.ec

        assert server_span.n == "tornado-server"
        assert server_span.data["http"]["status"] == 405
        assert testenv["tornado_server"] + "/405" == server_span.data["http"]["url"]
        assert not server_span.data["http"]["params"]
        assert server_span.data["http"]["method"] == "GET"

        assert client_span.n == "tornado-client"
        assert client_span.data["http"]["status"] == 405
        assert testenv["tornado_server"] + "/405" == client_span.data["http"]["url"]
        assert client_span.data["http"]["method"] == "GET"
        assert client_span.stack
        assert type(client_span.stack) is list
        assert len(client_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(server_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_get_500(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                try:
                    return await self.http_client.fetch(testenv["tornado_server"] + "/500")
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "tornado-server")
        client_span = get_first_span_by_name(spans, "tornado-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert client_span.ec == 1
        assert server_span.ec == 1

        assert server_span.n == "tornado-server"
        assert server_span.data["http"]["status"] == 500
        assert testenv["tornado_server"] + "/500" == server_span.data["http"]["url"]
        assert not server_span.data["http"]["params"]
        assert server_span.data["http"]["method"] == "GET"

        assert client_span.n == "tornado-client"
        assert client_span.data["http"]["status"] == 500
        assert testenv["tornado_server"] + "/500" == client_span.data["http"]["url"]
        assert client_span.data["http"]["method"] == "GET"
        assert client_span.stack
        assert type(client_span.stack) is list
        assert len(client_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(server_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_get_504(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                try:
                    return await self.http_client.fetch(testenv["tornado_server"] + "/504")
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "tornado-server")
        client_span = get_first_span_by_name(spans, "tornado-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert client_span.ec == 1
        assert server_span.ec == 1

        assert server_span.n == "tornado-server"
        assert server_span.data["http"]["status"] == 504
        assert testenv["tornado_server"] + "/504" == server_span.data["http"]["url"]
        assert not server_span.data["http"]["params"]
        assert server_span.data["http"]["method"] == "GET"

        assert client_span.n == "tornado-client"
        assert client_span.data["http"]["status"] == 504
        assert testenv["tornado_server"] + "/504" == client_span.data["http"]["url"]
        assert client_span.data["http"]["method"] == "GET"
        assert client_span.stack
        assert type(client_span.stack) is list
        assert len(client_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(server_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"

    def test_get_with_params_to_scrub(self) -> None:
        async def test():
            with tracer.start_as_current_span("test"):
                return await self.http_client.fetch(testenv["tornado_server"] + "/?secret=yeah")

        response = tornado.ioloop.IOLoop.current().run_sync(test)
        assert isinstance(response, tornado.httpclient.HTTPResponse)

        time.sleep(0.5)
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "tornado-server")
        client_span = get_first_span_by_name(spans, "tornado-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert not get_current_span().is_recording()

        # Same traceId
        traceId = test_span.t
        assert traceId == client_span.t
        assert traceId == server_span.t

        # Parent relationships
        assert client_span.p == test_span.s
        assert server_span.p == client_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        assert server_span.n == "tornado-server"
        assert server_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == server_span.data["http"]["url"]
        assert 'secret=<redacted>' == server_span.data["http"]["params"]
        assert server_span.data["http"]["method"] == "GET"

        assert client_span.n == "tornado-client"
        assert client_span.data["http"]["status"] == 200
        assert testenv["tornado_server"] + "/" == client_span.data["http"]["url"]
        assert 'secret=<redacted>' == client_span.data["http"]["params"]
        assert client_span.data["http"]["method"] == "GET"
        assert client_span.stack
        assert type(client_span.stack) is list
        assert len(client_span.stack) > 1

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(traceId)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(server_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == '1'
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(traceId)}"
