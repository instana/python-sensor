import uvicorn
from fastapi import FastAPI

from ...helpers import testenv

testenv["fastapi_port"] = 10816
testenv["fastapi_server"] = ("http://127.0.0.1:" + str(testenv["fastapi_port"]))

fastapi_server = FastAPI()

@fastapi_server.get("/")
async def root():
    return {"message": "Hello World"}


@fastapi_server.get("/users/{user_id}")
async def user(user_id):
    return {"user": user_id}