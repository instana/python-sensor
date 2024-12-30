# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles

dir_path = os.path.dirname(os.path.realpath(__file__))


def homepage(request):
    return PlainTextResponse("Hello, world!")


def user(request):
    user_id = request.path_params["user_id"]
    return PlainTextResponse("Hello, user id %s!" % user_id)


def response_headers(request):
    headers = {"X-Capture-This-Too": "this too", "X-Capture-That-Too": "that too"}
    return PlainTextResponse("Stan wuz here with headers!", headers=headers)


async def websocket_endpoint(websocket):
    await websocket.accept()
    await websocket.send_text("Hello, websocket!")
    await websocket.close()


def startup():
    print("Ready to go")


routes = [
    Route("/", homepage),
    Route("/users/{user_id}", user),
    Route("/response_headers", response_headers),
    WebSocketRoute("/ws", websocket_endpoint),
    Mount("/static", StaticFiles(directory=dir_path + "/static")),
]

starlette_server = Starlette(debug=True, routes=routes, on_startup=[startup])
