from __future__ import absolute_import

import time
import unittest

import grpc

import tests.apps.grpc_server.stan_pb2 as stan_pb2
import tests.apps.grpc_server.stan_pb2_grpc as stan_pb2_grpc

from instana.singletons import tracer
from .helpers import testenv


class TestGRPCIO(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.channel = grpc.insecure_channel('127.0.0.1:5030')
        self.server_stub = stan_pb2_grpc.StanStub(self.channel)
        # The grpc client apparently needs a second to connect and initialize
        time.sleep(1)

    def tearDown(self):
        """ Do nothing for now """
        pass

    def test_vanilla_request(self):
        response = self.server_stub.AskQuestion(stan_pb2.QuestionRequest(question="Are you there?"))
        self.assertEqual(response.answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

    def test_vanilla_request_via_with_call(self):
        response = self.server_stub.AskQuestion.with_call(stan_pb2.QuestionRequest(question="Are you there?"))
        self.assertEqual(response[0].answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

    def test_request(self):
        with tracer.start_active_span('test'):
            response = self.server_stub.AskQuestion(stan_pb2.QuestionRequest(question="Are you there?"))

        self.assertIsNone(tracer.active_span)
        self.assertIsNotNone(response)
        self.assertEqual(response.answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = spans[0]
        client_span = spans[1]
        test_span = spans[2]

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(client_span.error)
        self.assertIsNone(client_span.ec)
        self.assertFalse(server_span.error)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNotNone(server_span.stack)
        self.assertEqual(2, len(server_span.stack))

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data.sdk.name, 'test')

    def test_request_via_with_call(self):
        with tracer.start_active_span('test'):
            response = self.server_stub.AskQuestion.with_call(stan_pb2.QuestionRequest(question="Are you there?"))

        self.assertIsNone(tracer.active_span)
        self.assertIsNotNone(response)
        self.assertEqual(type(response), tuple)
        self.assertEqual(response[0].answer, "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka")

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        server_span = spans[0]
        client_span = spans[1]
        test_span = spans[2]

        # Same traceId
        self.assertEqual(server_span.t, client_span.t)
        self.assertEqual(server_span.t, test_span.t)

        # Parent relationships
        self.assertEqual(server_span.p, client_span.s)
        self.assertEqual(client_span.p, test_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(client_span.error)
        self.assertIsNone(client_span.ec)
        self.assertFalse(server_span.error)
        self.assertIsNone(server_span.ec)

        # rpc-server
        self.assertEqual(server_span.n, 'rpc-server')
        self.assertEqual(server_span.k, 1)
        self.assertIsNotNone(server_span.stack)
        self.assertEqual(2, len(server_span.stack))

        # rpc-client
        self.assertEqual(client_span.n, 'rpc-client')
        self.assertEqual(client_span.k, 2)
        self.assertIsNotNone(client_span.stack)

        # test-span
        self.assertEqual(test_span.n, 'sdk')
        self.assertEqual(test_span.data.sdk.name, 'test')
