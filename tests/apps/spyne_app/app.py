#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) Copyright IBM Corp. 2025

import logging

from wsgiref.simple_server import make_server
from spyne import Application, rpc, ServiceBase, Iterable, UnsignedInteger, \
    String, Unicode

from spyne.protocol.json import JsonDocument
from spyne.protocol.http import HttpRpc
from spyne.server.wsgi import WsgiApplication

from spyne.error import ResourceNotFoundError

from tests.helpers import testenv

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

testenv["spyne_port"] = 10818
testenv["spyne_server"] = ("http://127.0.0.1:" + str(testenv["spyne_port"]))

class HelloWorldService(ServiceBase):
    @rpc(String, UnsignedInteger, _returns=Iterable(String))
    def say_hello(ctx, name, times):
        """
        :param name: The name to say hello to
        :param times: The number of times to say hello

        :returns: An array of 'Hello, <name>' strings, repeated <times> times.
        """

        for i in range(times):
            yield 'Hello, %s' % name

    @rpc(_returns=Unicode)
    def hello(ctx):
        return "<center><h1>🐍 Hello Stan! 🦄</h1></center>"
    
    @rpc(_returns=Unicode)
    def response_headers(ctx):
        ctx.transport.add_header("X-Capture-This", "this")
        ctx.transport.add_header("X-Capture-That", "that")
        return "Stan wuz here with headers!"
    
    @rpc(UnsignedInteger)
    def custom_404(ctx, user_id):
        raise ResourceNotFoundError(user_id)
    
    @rpc()
    def exception(ctx):
        raise Exception('fake error')


application = Application([HelloWorldService], 'instana.spyne.service.helloworld',
    in_protocol=HttpRpc(validator='soft'),
    out_protocol=JsonDocument(ignore_wrappers=True),
)
wsgi_app = WsgiApplication(application)
spyne_server = make_server('127.0.0.1', testenv["spyne_port"], wsgi_app)

if __name__ == '__main__':
    spyne_server.request_queue_size = 20
    spyne_server.serve_forever()
