# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import instana
import uvicorn

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import requests
from starlette.middleware import Middleware
from starlette_context import context
from starlette.responses import JSONResponse

from starlette.requests import Request
from starlette_context.middleware import RawContextMiddleware

middleware = [
    Middleware(
        RawContextMiddleware,
    )
]

fastapi_server = FastAPI(middleware=middleware)


# @fastapi_server.exception_handler(StarletteHTTPException)
# async def http_exception_handler(request, exc):
#     return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

# @fastapi_server.exception_handler(RequestValidationError)
# async def validation_exception_handler(request, exc):
#     return PlainTextResponse(str(exc), status_code=400)

@fastapi_server.get("/")
async def root():
    return {"message": "Hello World"}

@fastapi_server.get("/users/{user_id}")
def user(user_id):
    return {"user": user_id}

@fastapi_server.get("/400")
async def four_zero_zero():
    raise HTTPException(status_code=400, detail="400 response")

@fastapi_server.get("/404")
async def four_zero_four():
    raise HTTPException(status_code=404, detail="Item not found")

@fastapi_server.get("/500")
async def five_hundred():
    raise HTTPException(status_code=500, detail="500 response")

@fastapi_server.get("/starlette_exception")
async def starlette_exception():
    raise StarletteHTTPException(status_code=500, detail="500 response")


@fastapi_server.get("/test_context")
async def index(request: Request):
    response = requests.get("http://0.0.0.0:8000/users/1", headers=context.data.get("instana_context"))
    return JSONResponse({**context.data["instana_context"], **response.headers})

uvicorn.run(fastapi_server, host="0.0.0.0")
