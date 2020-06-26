from wsgiref.simple_server import make_server
from pyramid.config import Configurator
import logging

from pyramid.response import Response
import pyramid.httpexceptions as exc

from ...helpers import testenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

testenv["pyramid_port"] = 10815
testenv["pyramid_server"] = ("http://127.0.0.1:" + str(testenv["pyramid_port"]))

def hello_world(request):
    return Response('Ok')

def please_fail(request):
    raise exc.HTTPInternalServerError("internal error")

def tableflip(request):
    raise BaseException("fake exception")

app = None
with Configurator() as config:
    config.add_tween('instana.instrumentation.pyramid.tweens.InstanaTweenFactory')
    config.add_route('hello', '/')
    config.add_view(hello_world, route_name='hello')
    config.add_route('fail', '/500')
    config.add_view(please_fail, route_name='fail')
    config.add_route('crash', '/exception')
    config.add_view(tableflip, route_name='crash')
    app = config.make_wsgi_app()
    
pyramid_server = make_server('127.0.0.1', testenv["pyramid_port"], app)

