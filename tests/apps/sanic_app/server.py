# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from sanic import Sanic
from sanic.response import text
from simpleview import SimpleView
from name import NameView
import instana

app = Sanic("My Hello, world app")

#
# @app.middleware("request")
# async def add_key(request):
#     # Arbitrary data may be stored in request context:
#     request.ctx.foo = "bar"


@app.middleware("response")
async def custom_banner(request, response):
    response.headers["Server"] = "Fake-Server"


@app.middleware("response")
async def prevent_xss(request, response):
    response.headers["x-xss-protection"] = "1; mode=block"


@app.route('/test', methods=["POST", "PUT"])
async def handler(request):
    return text('OK')


@app.get("/tag/<tag>")
async def tag_handler(request, tag):
    return text("Tag - {}".format(tag))


@app.get("/foo/<foo_id:int>")
async def uuid_handler(request, foo_id: int):
    return text("INT - {}".format(foo_id))


app.add_route(SimpleView.as_view(), "/")
app.add_route(NameView.as_view(), "/<name>")
