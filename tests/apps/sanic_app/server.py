# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import instana

from sanic import Sanic
from sanic.exceptions import SanicException
from sanic.response import text

from tests.apps.sanic_app.simpleview import SimpleView
from tests.apps.sanic_app.name import NameView

app = Sanic("test")


@app.get("/foo/<foo_id:int>")
async def uuid_handler(request, foo_id: int):
    return text("INT - {}".format(foo_id))


@app.route("/response_headers")
async def response_headers(request):
    headers = {"X-Capture-This-Too": "this too", "X-Capture-That-Too": "that too"}
    return text("Stan wuz here with headers!", headers=headers)


@app.route("/test_request_args")
async def test_request_args_500(request):
    raise SanicException("Something went wrong.", status_code=500)


@app.route("/instana_exception")
async def test_instana_exception(request):
    raise SanicException(description="Something went wrong.", status_code=500)


@app.route("/wrong")
async def test_request_args_400(request):
    raise SanicException(message="Something went wrong.", status_code=400)


@app.get("/tag/<tag>")
async def tag_handler(request, tag):
    return text("Tag - {}".format(tag))


app.add_route(SimpleView.as_view(), "/")
app.add_route(NameView.as_view(), "/<name>")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True, access_log=True)
