# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from fastapi import FastAPI, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException
from instana.span.span import get_current_span

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


@fastapi_server.get("/response_headers")
async def response_headers():
    headers = {"X-Capture-This-Too": "this too", "X-Capture-That-Too": "that too"}
    return Response("Stan wuz here with headers!", headers=headers)


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


def trigger_outgoing_call():
    # As TestClient() is based on httpx, and we don't support it yet,
    # we must pass the SDK trace_id and span_id to the ASGI server.
    span_context = get_current_span().get_span_context()
    headers = {
        "X-INSTANA-T": str(span_context.trace_id),
        "X-INSTANA-S": str(span_context.span_id),
    }
    client = TestClient(fastapi_server, headers=headers)
    response = client.get("/users/1")
    return response.json()


@fastapi_server.get("/non_async_simple")
def non_async_complex_call():
    response = trigger_outgoing_call()
    return response


@fastapi_server.get("/non_async_threadpool")
def non_async_threadpool():
    run_in_threadpool(trigger_outgoing_call)
    return {
        "message": "non async functions executed on a thread pool can't be followed through thread boundaries"
    }
