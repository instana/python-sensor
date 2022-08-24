""" Test application for running tests with middleware
"""
from sanic import Sanic
from sanic import response
from sanic.response import json
from instana.instrumentation.sanic_middleware import InstanaSanicMiddleware

app = Sanic(__name__)

InstanaSanicMiddleware(app)


@app.route("/", methods=["GET"])
async def index(request):
    return json({"instana": "Rocks", "message": "Hello world!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
