import asyncio
from aiohttp import web

from ..helpers import testenv

testenv["aiohttp_server"] = "http://127.0.0.1:5002"


def say_hello(request):
    return web.Response(text='Hello, world')


def four_hundred_one(request):
    return web.HTTPUnauthorized(reason="I must simulate errors.", text="Simulated server error.")


def five_hundred(request):
    return web.HTTPInternalServerError(reason="I must simulate errors.", text="Simulated server error.")


def run_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = web.Application(debug=False)
    app.add_routes([web.get('/', say_hello)])
    app.add_routes([web.get('/401', four_hundred_one)])
    app.add_routes([web.get('/500', five_hundred)])

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, 'localhost', 5002)

    loop.run_until_complete(site.start())
    loop.run_forever()
