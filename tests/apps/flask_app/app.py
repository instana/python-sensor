#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import logging

from opentelemetry.semconv.trace import SpanAttributes

from flask import jsonify, Response
from wsgiref.simple_server import make_server
from flask import Flask, redirect, render_template, render_template_string

try:
    import boto3
    from moto import mock_aws
except ImportError:
    # Doesn't matter.  We won't call routes using boto3
    # in test sets that don't install/test for it.
    pass

from tests.helpers import testenv
from instana.singletons import tracer

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

testenv["wsgi_port"] = 10811
testenv["wsgi_server"] = ("http://127.0.0.1:" + str(testenv["wsgi_port"]))

app = Flask(__name__)
app.debug = False
app.use_reloader = False

flask_server = make_server('127.0.0.1', testenv["wsgi_port"], app.wsgi_app)


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


class NotFound(Exception):
    status_code = 404

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.route("/")
def hello():
    return "<center><h1>🐍 Hello Stan! 🦄</h1></center>"


@app.route("/users/<username>/sayhello")
def username_hello(username):
    return u"<center><h1>🐍 Hello %s! 🦄</h1></center>" % username


@app.route("/complex")
def gen_opentelemetry():
    with tracer.start_as_current_span("asteroid") as pspan:
        pspan.set_attribute(SpanAttributes.COMPONENT, "Python simple example app")
        pspan.set_attribute(
            SpanAttributes.SPAN_KIND, SpanAttributes.SPAN_KIND_RPC_SERVER
        )
        pspan.set_attribute(SpanAttributes.PEER_HOSTNAME, "localhost")
        pspan.set_attribute(SpanAttributes.HTTP_URL, "/python/simple/one")
        pspan.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        pspan.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 200)
        pspan.add_event(name="gen_opentelemetry", attributes={"foo": "bar"})

        span_context = pspan.get_span_context()

        with tracer.start_active_span("spacedust", span_context=span_context) as cspan:
            cspan.set_attribute(
                SpanAttributes.SPAN_KIND, SpanAttributes.SPAN_KIND_RPC_CLIENT
            )
            cspan.set_attribute(SpanAttributes.PEER_HOSTNAME, "localhost")
            cspan.set_attribute(SpanAttributes.HTTP_URL, "/python/simple/two")
            cspan.set_attribute(SpanAttributes.HTTP_METHOD, "POST")
            cspan.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 204)
            cspan.set_baggage_item("someBaggage", "someValue")

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


@app.route("/custom-404")
def custom404():
    raise NotFound("My custom 404 message")


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


@app.route("/exception-invalid-usage")
def exception_invalid_usage():
    raise InvalidUsage("Simulated custom exception", status_code=502)


@app.route("/render")
def render():
    return render_template('flask_render_template.html', name="Peter")


@app.route("/render_string")
def render_string():
    return render_template_string('hello {{ what }}', what='world')


@app.route("/render_error")
def render_error():
    return render_template('flask_render_error.html', what='world')


@app.route("/response_headers")
def response_headers():
    headers = {
        'X-Capture-This': 'Ok',
        'X-Capture-That': 'Ok too'
    }
    return Response("Stan wuz here with headers!", headers=headers)

@app.route("/boto3/sqs")
def boto3_sqs():
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'

    with mock_aws():
        boto3_client = boto3.client('sqs', region_name='us-east-1')
        response = boto3_client.create_queue(
            QueueName='SQS_QUEUE_NAME',
            Attributes={
                'DelaySeconds': '60',
                'MessageRetentionPeriod': '600'
            }
        )

        queue_url = response['QueueUrl']
        response = boto3_client.send_message(
                QueueUrl=queue_url,
                DelaySeconds=10,
                MessageAttributes={
                    'Website': {
                        'DataType': 'String',
                        'StringValue': 'https://www.instana.com'
                    },
                },
                MessageBody=('Monitor any application, service, or request '
                            'with Instana Application Performance Monitoring')
            )
        return Response(response)

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    logger.error("InvalidUsage error handler invoked")
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.errorhandler(404)
@app.errorhandler(NotFound)
def handle_not_found(e):
    return "blah: %s" % str(e), 404


if __name__ == '__main__':
    flask_server.request_queue_size = 20
    flask_server.serve_forever()
