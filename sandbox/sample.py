from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response
import instana  # noqa: F401


def hello_world(request):
    return Response("Hello World!", status=500)


if __name__ == "__main__":
    with Configurator() as config:
        config.add_route("hello", "/")
        config.add_view(hello_world, route_name="hello")
        app = config.make_wsgi_app()
    server = make_server("0.0.0.0", 6543, app)
    server.serve_forever()
