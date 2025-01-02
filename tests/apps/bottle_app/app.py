#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) Copyright IBM Corp. 2024

import logging

from wsgiref.simple_server import make_server
from bottle import default_app, response

from tests.helpers import testenv
from instana.middleware import InstanaWSGIMiddleware

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

testenv["wsgi_port"] = 10812
testenv["wsgi_server"] = ("http://127.0.0.1:" + str(testenv["wsgi_port"]))

app = default_app()

@app.route("/")
def hello():
    return "<center><h1>🐍 Hello Stan! 🦄</h1></center>"

@app.route("/response_headers")
def response_headers():
    response.set_header("X-Capture-This", "this")
    response.set_header("X-Capture-That", "that")
    return "Stan wuz here with headers!"

# Wrap the application with the Instana WSGI Middleware
app = InstanaWSGIMiddleware(app)
bottle_server = make_server('127.0.0.1', testenv["wsgi_port"], app)

if __name__ == "__main__":
    bottle_server.request_queue_size = 20
    bottle_server.serve_forever()
