# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

import os
import asyncio
# TODO: Change asynqp to aio-pika once it is fully supported
import asynqp
from aiohttp import web

RABBITMQ_HOST = ""
if "RABBITMQ_HOST" in os.environ:
    RABBITMQ_HOST = os.environ["RABBITMQ_HOST"]
else:
    RABBITMQ_HOST = "localhost"


class RabbitUtil():
    def __init__(self, loop):
        self.loop = loop
        self.loop.run_until_complete(self.connect())

    @asyncio.coroutine
    def connect(self):
        # connect to the RabbitMQ broker
        self.connection = yield from asynqp.connect(RABBITMQ_HOST, 5672, username='guest', password='guest')

        # Open a communications channel
        self.channel = yield from self.connection.open_channel()

        # Create a queue and an exchange on the broker
        self.exchange = yield from self.channel.declare_exchange('test.exchange', 'direct')
        self.queue = yield from self.channel.declare_queue('test.queue')

        # Bind the queue to the exchange, so the queue will get messages published to the exchange
        yield from self.queue.bind(self.exchange, 'routing.key')
        yield from self.queue.purge()


@asyncio.coroutine
def publish_msg(request):
    msg = asynqp.Message({'hello': 'world'})
    rabbit_util.exchange.publish(msg, 'routing.key')
    rabbit_util.exchange.publish(msg, 'routing.key')
    rabbit_util.exchange.publish(msg, 'routing.key')
    rabbit_util.exchange.publish(msg, 'routing.key')

    msg = yield from rabbit_util.queue.get()

    return web.Response(text='Published 4 messages. Got 1. %s' % str(msg))


async def say_hello(request):
    return web.Response(text='Hello, world')


async def four_hundred_one(request):
    return web.HTTPUnauthorized(reason="I must simulate errors.", text="Simulated server error.")


async def five_hundred(request):
    return web.HTTPInternalServerError(reason="I must simulate errors.", text="Simulated server error.")


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

rabbit_util = RabbitUtil(loop)

app = web.Application(debug=False)
app.add_routes([web.get('/', say_hello)])
app.add_routes([web.get('/401', four_hundred_one)])
app.add_routes([web.get('/500', five_hundred)])
app.add_routes([web.get('/publish', publish_msg)])

runner = web.AppRunner(app)
loop.run_until_complete(runner.setup())
site = web.TCPSite(runner, 'localhost', 5102)

loop.run_until_complete(site.start())
loop.run_forever()

