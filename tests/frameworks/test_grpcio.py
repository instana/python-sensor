# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import time
import unittest
import random

import grpc

import tests.apps.grpc_server
import tests.apps.grpc_server.stan_pb2 as stan_pb2
import tests.apps.grpc_server.stan_pb2_grpc as stan_pb2_grpc

from instana.singletons import tracer
from ..helpers import testenv, get_first_span_by_name


class TestGRPCIO(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.channel = grpc.insecure_channel(testenv["grpc_server"])
        self.server_stub = stan_pb2_grpc.StanStub(self.channel)
        # The grpc client apparently needs a second to connect and initialize
        time.sleep(1)

    def tearDown(self):
        """ Do nothing for now """
        pass

    def generate_questions(self):
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

    def test_vanilla_request(self):
        response = self.server_stub.OneQuestionOneResponse(stan_pb2.QuestionRequest(question="Are you there?"))
        self.assertEqual(response.answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

    def test_vanilla_request_via_with_call(self):
        response = self.server_stub.OneQuestionOneResponse.with_call(stan_pb2.QuestionRequest(question="Are you there?"))
        self.assertEqual(response[0].answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

    def test_unary_one_to_one(self):
        with tracer.start_active_span('test'):
            response = self.server_stub.OneQuestionOneResponse(stan_pb2.QuestionRequest(question="Are you there?"))

        self.assertIsNone(tracer.active_span)
        self.assertIsNotNone(response)
        self.assertEqual(response.answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/OneQuestionOneResponse')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/OneQuestionOneResponse')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'unary')
        self.assertIsNone(client_span.data["rpc"]["error"])

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

    def test_streaming_many_to_one(self):

        with tracer.start_active_span('test'):
            response = self.server_stub.ManyQuestionsOneResponse(self.generate_questions())

        self.assertIsNone(tracer.active_span)
        self.assertIsNotNone(response)

        self.assertEqual('Ok', response.answer)
        self.assertEqual(True, response.was_answered)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/ManyQuestionsOneResponse')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/ManyQuestionsOneResponse')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'stream')
        self.assertIsNone(client_span.data["rpc"]["error"])

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

    def test_streaming_one_to_many(self):

        with tracer.start_active_span('test'):
            responses = self.server_stub.OneQuestionManyResponses(stan_pb2.QuestionRequest(question="Are you there?"))

        self.assertIsNone(tracer.active_span)
        self.assertIsNotNone(responses)

        final_answers = []
        for response in responses:
            final_answers.append(response)

        self.assertEqual(len(final_answers), 6)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/OneQuestionManyResponses')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/OneQuestionManyResponses')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'stream')
        self.assertIsNone(client_span.data["rpc"]["error"])

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

    def test_streaming_many_to_many(self):
        with tracer.start_active_span('test'):
            responses = self.server_stub.ManyQuestionsManyReponses(self.generate_questions())

        self.assertIsNone(tracer.active_span)
        self.assertIsNotNone(responses)

        final_answers = []
        for response in responses:
            final_answers.append(response)

        self.assertEqual(len(final_answers), 6)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/ManyQuestionsManyReponses')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/ManyQuestionsManyReponses')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'stream')
        self.assertIsNone(client_span.data["rpc"]["error"])

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

    def test_unary_one_to_one_with_call(self):
        with tracer.start_active_span('test'):
            response = self.server_stub.OneQuestionOneResponse.with_call(stan_pb2.QuestionRequest(question="Are you there?"))

        self.assertIsNone(tracer.active_span)
        self.assertIsNotNone(response)
        self.assertEqual(type(response), tuple)
        self.assertEqual(response[0].answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/OneQuestionOneResponse')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/OneQuestionOneResponse')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'unary')
        self.assertIsNone(client_span.data["rpc"]["error"])

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

    def test_streaming_many_to_one_with_call(self):
        with tracer.start_active_span('test'):
            response = self.server_stub.ManyQuestionsOneResponse.with_call(self.generate_questions())

        self.assertIsNone(tracer.active_span)
        self.assertIsNotNone(response)

        self.assertEqual('Ok', response[0].answer)
        self.assertEqual(True, response[0].was_answered)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/ManyQuestionsOneResponse')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/ManyQuestionsOneResponse')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'stream')
        self.assertIsNone(client_span.data["rpc"]["error"])

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

    def test_async_unary(self):
        def process_response(future):
            result = future.result()
            self.assertEqual(type(result), stan_pb2.QuestionResponse)
            self.assertTrue(result.was_answered)
            self.assertEqual(result.answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

        with tracer.start_active_span('test'):
            future = self.server_stub.OneQuestionOneResponse.future(
                stan_pb2.QuestionRequest(question="Are you there?"))
            future.add_done_callback(process_response)
            time.sleep(0.7)

        self.assertIsNone(tracer.active_span)
        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/OneQuestionOneResponse')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/OneQuestionOneResponse')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'unary')
        self.assertIsNone(client_span.data["rpc"]["error"])

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

    def test_async_stream(self):
        def process_response(future):
            result = future.result()
            self.assertEqual(type(result), stan_pb2.QuestionResponse)
            self.assertTrue(result.was_answered)
            self.assertEqual(result.answer, 'Ok')

        with tracer.start_active_span('test'):
            future = self.server_stub.ManyQuestionsOneResponse.future(self.generate_questions())
            future.add_done_callback(process_response)

        # The question generator delays at random intervals between questions so to assure that
        # all questions are sent and processed before we start testing the results.
        time.sleep(5)

        self.assertIsNone(tracer.active_span)
        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(client_span.ec)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/ManyQuestionsOneResponse')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/ManyQuestionsOneResponse')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'stream')
        self.assertIsNone(client_span.data["rpc"]["error"])

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

    def test_server_error(self):
        response = None
        with tracer.start_active_span('test'):
            try:
                response = self.server_stub.OneQuestionOneErrorResponse(stan_pb2.QuestionRequest(question="Do u error?"))
            except:
                pass

        self.assertIsNone(tracer.active_span)
        self.assertIsNone(response)

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        log_span = get_first_span_by_name(spans, 'log')
        server_span = get_first_span_by_name(spans, 'rpc-server')
        client_span = get_first_span_by_name(spans, 'rpc-client')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert(log_span)
        assert(server_span)
        assert(client_span)
        assert(test_span)

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertEqual(client_span.ec, 1)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNone(server_span.stack)
        self.assertEqual(server_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(server_span.data["rpc"]["call"], '/stan.Stan/OneQuestionOneErrorResponse')
        self.assertEqual(server_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(server_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertIsNone(server_span.data["rpc"]["error"])

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)
        self.assertEqual(client_span.data["rpc"]["flavor"], 'grpc')
        self.assertEqual(client_span.data["rpc"]["call"], '/stan.Stan/OneQuestionOneErrorResponse')
        self.assertEqual(client_span.data["rpc"]["host"], testenv["grpc_host"])
        self.assertEqual(client_span.data["rpc"]["port"], str(testenv["grpc_port"]))
        self.assertEqual(client_span.data["rpc"]["call_type"], 'unary')
        self.assertIsNotNone(client_span.data["rpc"]["error"])

        # log
        self.assertEqual(log_span.n, 'log')
        self.assertIsNotNone(log_span.data["log"])
        self.assertEqual(log_span.data["log"]['message'], 'Exception calling application: Simulated error')

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data["sdk"]["name"], 'test')
