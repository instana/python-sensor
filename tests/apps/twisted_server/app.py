#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) Copyright IBM Corp. 2026

from twisted.internet import reactor
from twisted.web import server
from twisted.web.client import Agent, readBody
from twisted.web.http import Request
from twisted.web.http_headers import Headers
from twisted.web.resource import Resource

from tests.helpers import testenv


class RootResource(Resource):
    isLeaf = True

    def render_GET(self, request: Request) -> bytes:
        return b"Hello Twisted"

    def render_POST(self, request: Request) -> bytes:
        return b"Hello Twisted post"


class R301Resource(Resource):
    isLeaf = True

    def render_GET(self, request: Request) -> bytes:
        request.setResponseCode(301)
        request.setHeader(b"location", b"/")
        return b""


class R404Resource(Resource):
    isLeaf = True

    def render_GET(self, request: Request) -> bytes:
        request.setResponseCode(404)
        return b"Not Found"


class R500Resource(Resource):
    isLeaf = True

    def render_GET(self, request: Request) -> bytes:
        request.setResponseCode(500)
        return b"Internal Server Error"


class ResponseHeadersResource(Resource):
    isLeaf = True

    def render_GET(self, request: Request) -> bytes:
        request.setHeader(b"X-Capture-This-Too", b"this too")
        request.setHeader(b"X-Capture-That-Too", b"that too")
        return b"Stan wuz here with headers!"


class FetchResource(Resource):
    """GET /fetch?url=<target> — makes an outbound Agent.request so
    twisted-client instrumentation is exercised from within the reactor."""

    isLeaf = True

    def render_GET(self, request: Request) -> bytes:
        target = request.args.get(b"url", [None])[0]
        if not target:
            request.setResponseCode(400)
            return b"missing url param"

        agent_obj = Agent(reactor)
        d = agent_obj.request(b"GET", target, Headers({}), None)

        def on_response(response: object) -> object:
            return readBody(response)

        def on_body(body: bytes) -> None:
            request.write(b"Fetched: " + body)
            request.finish()

        def on_error(failure: object) -> None:
            request.setResponseCode(502)
            request.write(b"Fetch error: " + failure.getErrorMessage().encode())
            request.finish()

        d.addCallback(on_response)
        d.addCallback(on_body)
        d.addErrback(on_error)
        return server.NOT_DONE_YET


class TwistedApp(Resource):
    """Root resource that dispatches to child resources by path."""

    def getChild(self, path: bytes, request: Request) -> Resource:
        if path == b"":
            # /  — serve root
            return RootResource()
        if path == b"301":
            return R301Resource()
        if path == b"404":
            return R404Resource()
        if path == b"500":
            return R500Resource()
        if path == b"response_headers":
            return ResponseHeadersResource()
        if path == b"fetch":
            return FetchResource()
        return Resource.getChild(self, path, request)

    def render_GET(self, request: Request) -> bytes:
        return b"Hello Twisted"

    def render_POST(self, request: Request) -> bytes:
        return b"Hello Twisted post"


def run_server() -> None:
    root = TwistedApp()
    site = server.Site(root)
    reactor.listenTCP(testenv["twisted_port"], site)
    reactor.run(installSignalHandlers=False)
