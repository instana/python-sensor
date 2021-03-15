#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os.path
import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web

import asyncio

from ...helpers import testenv


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/301", R301Handler),
            (r"/405", R405Handler),
            (r"/500", R500Handler),
            (r"/504", R504Handler),
        ]
        settings = dict(
            cookie_secret="7FpA2}3dgri2GEDr",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=False,
            debug=True,
            autoreload=False,
            autoescape=None,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello Tornado")

    def post(self):
        self.write("Hello Tornado post")


class R301Handler(tornado.web.RequestHandler):
    def get(self):
        self.redirect("/", permanent=True)


class R405Handler(tornado.web.RequestHandler):
    def get(self):
        self.write("Simulated Method not allowed")
        self.set_status(405)


class R500Handler(tornado.web.RequestHandler):
    def get(self):
        raise tornado.web.HTTPError(log_message="Simulated Internal Server Errors")


class R504Handler(tornado.web.RequestHandler):
    def get(self):
        raise tornado.web.HTTPError(status_code=504, log_message="Simulated Internal Server Errors")


def run_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(testenv["tornado_port"])
    tornado.ioloop.IOLoop.current().start()
