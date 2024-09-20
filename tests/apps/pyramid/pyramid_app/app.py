# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from wsgiref.simple_server import make_server
from pyramid.config import Configurator
import logging

from pyramid.response import Response
import pyramid.httpexceptions as exc

from tests.helpers import testenv

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


def hello_user(request):
    user = request.matchdict["user"]
    return Response(f"Hello {user}!")


app = None
settings = {
    "pyramid.tweens": "tests.apps.pyramid.pyramid_utils.tweens.timing_tween_factory",
}
with Configurator(settings=settings) as config:
    config.add_route("hello", "/")
    config.add_view(hello_world, route_name="hello")
    config.add_route("fail", "/500")
    config.add_view(please_fail, route_name="fail")
    config.add_route("crash", "/exception")
    config.add_view(tableflip, route_name="crash")
    config.add_route("response_headers", "/response_headers")
    config.add_view(response_headers, route_name="response_headers")
    config.add_route("hello_user", "/hello_user/{user}")
    config.add_view(hello_user, route_name="hello_user")
    app = config.make_wsgi_app()

pyramid_server = make_server("127.0.0.1", testenv["pyramid_port"], app)
