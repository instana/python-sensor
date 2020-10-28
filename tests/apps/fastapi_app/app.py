from fastapi import FastAPI

fastapi_server = FastAPI()

@fastapi_server.get("/")
async def root():
    return {"message": "Hello World"}


@fastapi_server.get("/users/{user_id}")
async def user(user_id):
    return {"user": user_id}