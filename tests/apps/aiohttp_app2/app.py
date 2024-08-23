#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) Copyright IBM Corp. 2024

import asyncio

from aiohttp import web

from tests.helpers import testenv

testenv["aiohttp_port"] = 10810
testenv["aiohttp_server"] = f"http://127.0.0.1:{testenv['aiohttp_port']}"


def say_hello(request):
    return web.Response(text="Hello, world")


@web.middleware
async def middleware1(request, handler):
    print("Middleware 1 called")
    response = await handler(request)
    print("Middleware 1 finished")
    return response


def aiohttp_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = web.Application(middlewares=[middleware1])
    app.add_routes([web.get("/", say_hello)])

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "127.0.0.1", testenv["aiohttp_port"])

    loop.run_until_complete(site.start())
    loop.run_forever()
