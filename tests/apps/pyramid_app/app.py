# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import logging
from wsgiref.simple_server import make_server

import pyramid.httpexceptions as exc
from pyramid.config import Configurator
from pyramid.response import Response

from ...helpers import testenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

testenv["pyramid_port"] = 10815
testenv["pyramid_server"] = "http://127.0.0.1:" + str(testenv["pyramid_port"])


def hello_world(request):
    return Response("Ok")


def please_fail(request):
    raise exc.HTTPInternalServerError("internal error")


def tableflip(request):
    raise BaseException("fake exception")


def response_headers(request):
    headers = {"X-Capture-This": "Ok", "X-Capture-That": "Ok too"}
    return Response("Stan wuz here with headers!", headers=headers)


app = None
with Configurator() as config:
    config.add_tween("instana.instrumentation.pyramid.tweens.InstanaTweenFactory")
    config.add_route("hello", "/")
    config.add_view(hello_world, route_name="hello")
    config.add_route("fail", "/500")
    config.add_view(please_fail, route_name="fail")
    config.add_route("crash", "/exception")
    config.add_view(tableflip, route_name="crash")
    config.add_route("response_headers", "/response_headers")
    config.add_view(response_headers, route_name="response_headers")
    app = config.make_wsgi_app()

pyramid_server = make_server("127.0.0.1", testenv["pyramid_port"], app)
