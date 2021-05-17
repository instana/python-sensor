# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from sanic import Sanic
from sanic.log import logger
from simpleview import SimpleView
from name import NameView
from sanic.response import text, json
import instana

app = Sanic('test')

@app.get("/foo/<foo_id:int>")
async def uuid_handler(request, foo_id: int):
    return text("INT - {}".format(foo_id))


@app.route("/test_request_args")
async def test_request_args(request):
    return json({
        "parsed": True,
        "url": request.url,
        "query_string": request.query_string,
        "args": request.raw_args,
        "query_args": request.query_args,
    })


@app.get("/tag/<tag>")
async def tag_handler(request, tag):
    return text("Tag - {}".format(tag))


app.add_route(SimpleView.as_view(), "/")
app.add_route(NameView.as_view(), "/<name>")


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000, debug=True, access_log=True)



