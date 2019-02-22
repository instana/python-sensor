import asyncio
from aiohttp import web

from ..helpers import testenv

testenv["aiohttp_server"] = "http://127.0.0.1:5002"


def say_hello(request):
    return web.Response(text='Hello, world')


def run_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = web.Application(debug=True)
    app.add_routes([web.get('/', say_hello)])

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, 'localhost', 5002)

    loop.run_until_complete(site.start())
    loop.run_forever()
