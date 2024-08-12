# (c) Copyright IBM Corp. 2024

import os

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route

dir_path = os.path.dirname(os.path.realpath(__file__))


def homepage(request):
    return PlainTextResponse("Hello, world!")


def five_hundred(request):
    return PlainTextResponse("Something went wrong!", status_code=500)


def startup():
    print("Ready to go")


routes = [
    Route("/", homepage),
    Route("/five", five_hundred),
]

starlette_server = Starlette(
    debug=True,
    routes=routes,
    on_startup=[startup],
    middleware=[
        Middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"],
        ),
    ],
)
