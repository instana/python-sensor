# (c) Copyright IBM Corp. 2024

from fastapi import FastAPI, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware import Middleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware


fastapi_server = FastAPI(
    middleware=[
        Middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"],
        ),
    ],
)


@fastapi_server.get("/")
async def root():
    return {"message": "Hello World"}
