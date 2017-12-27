#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import Flask
app = Flask(__name__)
app.debug = False
app.use_reloader = False


@app.route("/")
def hello():
    return "<center><h1>🐍 Hello Stan! 🦄</h1></center>"


@app.route("/400")
def fourhundred():
    return "Bad Request", 400


@app.route("/405")
def fourhundredfive():
    return "Method not allowed", 405


@app.route("/500")
def fivehundred():
    return "Internal Server Error", 500


@app.route("/504")
def fivehundredfour():
    return "Gateway Timeout", 504


@app.route("/exception")
def exception():
    raise Exception('fake error')


if __name__ == '__main__':
    app.run()
