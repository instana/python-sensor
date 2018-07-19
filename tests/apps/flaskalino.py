#!/usr/bin/env python
# -*- coding: utf-8 -*-
import opentracing
import opentracing.ext.tags as ext
from flask import Flask, redirect
from instana import wsgi

from gevent.pywsgi import WSGIServer

app = Flask(__name__)
app.debug = False
app.use_reloader = False


@app.route("/")
def hello():
    return "<center><h1>🐍 Hello Stan! 🦄</h1></center>"


@app.route("/complex")
def gen_opentracing():
    with opentracing.tracer.start_active_span('asteroid') as pscope:
        pscope.span.set_tag(ext.COMPONENT, "Python simple example app")
        pscope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
        pscope.span.set_tag(ext.PEER_HOSTNAME, "localhost")
        pscope.span.set_tag(ext.HTTP_URL, "/python/simple/one")
        pscope.span.set_tag(ext.HTTP_METHOD, "GET")
        pscope.span.set_tag(ext.HTTP_STATUS_CODE, 200)
        pscope.span.log_kv({"foo": "bar"})

        with opentracing.tracer.start_active_span('spacedust', child_of=pscope.span) as cscope:
            cscope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_CLIENT)
            cscope.span.set_tag(ext.PEER_HOSTNAME, "localhost")
            cscope.span.set_tag(ext.HTTP_URL, "/python/simple/two")
            cscope.span.set_tag(ext.HTTP_METHOD, "POST")
            cscope.span.set_tag(ext.HTTP_STATUS_CODE, 204)
            cscope.span.set_baggage_item("someBaggage", "someValue")

    return "<center><h1>🐍 Generated some OT spans... 🦄</h1></center>"


@app.route("/301")
def threehundredone():
    return redirect('/', code=301)


@app.route("/302")
def threehundredtwo():
    return redirect('/', code=302)


@app.route("/400")
def fourhundred():
    return "Simulated Bad Request", 400


@app.route("/405")
def fourhundredfive():
    return "Simulated Method not allowed", 405


@app.route("/500")
def fivehundred():
    return "Simulated Internal Server Error", 500


@app.route("/504")
def fivehundredfour():
    return "Simulated Gateway Timeout", 504


@app.route("/exception")
def exception():
    raise Exception('fake error')


if __name__ == '__main__':
    app.wsgi_app = wsgi.iWSGIMiddleware(app.wsgi_app)
    # werkzeug_opts = {"threaded": True}
    # # app.run(debug=False, options=werkzeug_opts)
    # app.run(debug=False, threaded=True)
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()
