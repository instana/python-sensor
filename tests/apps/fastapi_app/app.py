# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

fastapi_server = FastAPI()

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
async def user(user_id):
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