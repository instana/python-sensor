from __future__ import absolute_import

import time
import random

import grpc
import stan_pb2
import stan_pb2_grpc

from instana.singletons import tracer

testenv = dict()
testenv["grpc_port"] = 10814
testenv["grpc_host"] = "127.0.0.1"
testenv["grpc_server"] = testenv["grpc_host"] + ":" + str(testenv["grpc_port"])


def generate_questions():
    """ Used in the streaming grpc tests """
    questions = [
        stan_pb2.QuestionRequest(question="Are you there?"),
        stan_pb2.QuestionRequest(question="What time is it?"),
        stan_pb2.QuestionRequest(question="Where in the world is Waldo?"),
        stan_pb2.QuestionRequest(question="What did one campfire say to the other?"),
        stan_pb2.QuestionRequest(question="Is cereal soup?"),
        stan_pb2.QuestionRequest(question="What is always coming, but never arrives?")
    ]
    for q in questions:
        yield q
        time.sleep(random.uniform(0.2, 0.5))


channel = grpc.insecure_channel(testenv["grpc_server"])
server_stub = stan_pb2_grpc.StanStub(channel)
# The grpc client apparently needs a second to connect and initialize
time.sleep(1)

with tracer.start_active_span('http-server') as scope:
    scope.span.set_tag('http.url', 'https://localhost:8080/grpc-client')
    scope.span.set_tag('http.method', 'GET')
    scope.span.set_tag('span.kind', 'entry')
    response = server_stub.OneQuestionOneResponse(stan_pb2.QuestionRequest(question="Are you there?"))

with tracer.start_active_span('http-server') as scope:
    scope.span.set_tag('http.url', 'https://localhost:8080/grpc-server-streaming')
    scope.span.set_tag('http.method', 'GET')
    scope.span.set_tag('span.kind', 'entry')
    responses = server_stub.OneQuestionManyResponses(stan_pb2.QuestionRequest(question="Are you there?"))

with tracer.start_active_span('http-server') as scope:
    scope.span.set_tag('http.url', 'https://localhost:8080/grpc-client-streaming')
    scope.span.set_tag('http.method', 'GET')
    scope.span.set_tag('span.kind', 'entry')
    response = server_stub.ManyQuestionsOneResponse(generate_questions())
