# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles

import os 
dir_path = os.path.dirname(os.path.realpath(__file__))

def homepage(request):
    return PlainTextResponse('Hello, world!')

def user(request):
    user_id = request.path_params['user_id']
    return PlainTextResponse('Hello, user id %s!' % user_id)

async def websocket_endpoint(websocket):
    await websocket.accept()
    await websocket.send_text('Hello, websocket!')
    await websocket.close()

def startup():
    print('Ready to go')


routes = [
    Route('/', homepage),
    Route('/users/{user_id}', user),
    WebSocketRoute('/ws', websocket_endpoint),
    Mount('/static', StaticFiles(directory=dir_path + "/static")),
]

starlette_server = Starlette(debug=True, routes=routes, on_startup=[startup])