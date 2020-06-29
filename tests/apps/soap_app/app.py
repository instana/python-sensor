#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging

from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server
from spyne import (Application, Fault, Integer, Iterable, ServiceBase, Unicode, rpc)

from ...helpers import testenv
from instana.wsgi import iWSGIMiddleware


testenv["soap_port"] = 10812
testenv["soap_server"] = ("http://127.0.0.1:" + str(testenv["soap_port"]))


# Simple in test suite SOAP server to test suds client instrumentation against.
# Configured to listen on localhost port 4132
# WSDL: http://localhost:4232/?wsdl
class StanSoapService(ServiceBase):
    @rpc(Unicode, Integer, _returns=Iterable(Unicode))
    def ask_question(ctx, question, answer):
        """Ask Stan a question!
        <b>Ask Stan questions as a Service</b>

        @param name the name to say hello to
        @param times the number of times to say hello
        @return the completed array
        """

        yield u'To an artificial mind, all reality is virtual. How do they know that the real world isn\'t just another simulation? How do you?'

    @rpc()
    def server_exception(ctx):
        raise Exception("Server side exception example.")

    @rpc()
    def server_fault(ctx):
        raise Fault("Server", "Server side fault example.")

    @rpc()
    def client_fault(ctx):
        raise Fault("Client", "Client side fault example")


# logging.basicConfig(level=logging.WARN)
logging.getLogger('suds').setLevel(logging.WARN)
logging.getLogger('suds.resolver').setLevel(logging.WARN)
logging.getLogger('spyne.protocol.xml').setLevel(logging.WARN)
logging.getLogger('spyne.model.complex').setLevel(logging.WARN)
logging.getLogger('spyne.interface._base').setLevel(logging.WARN)
logging.getLogger('spyne.interface.xml').setLevel(logging.WARN)
logging.getLogger('spyne.util.appreg').setLevel(logging.WARN)

app = Application([StanSoapService], 'instana.tests.app.ask_question',
                  in_protocol=Soap11(validator='lxml'), out_protocol=Soap11())

# Use Instana middleware so we can test context passing and Soap server traces.
wsgi_app = iWSGIMiddleware(WsgiApplication(app))
soapserver = make_server('127.0.0.1', testenv["soap_port"], wsgi_app)

if __name__ == '__main__':
    soapserver.serve_forever()
