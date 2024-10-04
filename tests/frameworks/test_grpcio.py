# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
import random
from typing import Generator

import pytest
import grpc

from opentelemetry.trace import SpanKind

import tests.apps.grpc_server  # noqa: F401
import tests.apps.grpc_server.stan_pb2 as stan_pb2
import tests.apps.grpc_server.stan_pb2_grpc as stan_pb2_grpc
from tests.helpers import testenv, get_first_span_by_name

from instana.singletons import tracer, agent
from instana.span.span import get_current_span


class TestGRPCIO:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.channel = grpc.insecure_channel(testenv["grpc_server"])
        self.server_stub = stan_pb2_grpc.StanStub(self.channel)
        # The grpc client apparently needs a second to connect and initialize
        time.sleep(1)
        yield
        # tearDown
        # Ensure that allow_exit_as_root has the default value
        agent.options.allow_exit_as_root = False

    def generate_questions(self) -> Generator[None, None, None]:
        """Used in the streaming grpc tests"""
        questions = [
            stan_pb2.QuestionRequest(question="Are you there?"),
            stan_pb2.QuestionRequest(question="What time is it?"),
            stan_pb2.QuestionRequest(question="Where in the world is Waldo?"),
            stan_pb2.QuestionRequest(
                question="What did one campfire say to the other?"
            ),
            stan_pb2.QuestionRequest(question="Is cereal soup?"),
            stan_pb2.QuestionRequest(
                question="What is always coming, but never arrives?"
            ),
        ]
        for q in questions:
            yield q
            time.sleep(random.uniform(0.2, 0.5))

    def test_vanilla_request(self) -> None:
        response = self.server_stub.OneQuestionOneResponse(
            stan_pb2.QuestionRequest(question="Are you there?")
        )
        assert (
            response.answer
            == "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka"
        )

    def test_vanilla_request_via_with_call(self) -> None:
        response = self.server_stub.OneQuestionOneResponse.with_call(
            stan_pb2.QuestionRequest(question="Are you there?")
        )
        assert (
            response[0].answer
            == "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka"
        )

    def test_unary_one_to_one(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.server_stub.OneQuestionOneResponse(
                stan_pb2.QuestionRequest(question="Are you there?")
            )

        assert not get_current_span().is_recording()
        assert response
        assert (
            response.answer
            == "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka"
        )

        spans = self.recorder.queued_spans()

        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneResponse"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert client_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneResponse"
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "unary"
        assert not client_span.data["rpc"]["error"]

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_streaming_many_to_one(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.server_stub.ManyQuestionsOneResponse(
                self.generate_questions()
            )

        assert not get_current_span().is_recording()
        assert response

        assert response.answer == "Ok"
        assert response.was_answered

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/ManyQuestionsOneResponse"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert client_span.data["rpc"]["call"] == "/stan.Stan/ManyQuestionsOneResponse"
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "stream"
        assert not client_span.data["rpc"]["error"]

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_streaming_one_to_many(self) -> None:
        with tracer.start_as_current_span("test"):
            responses = self.server_stub.OneQuestionManyResponses(
                stan_pb2.QuestionRequest(question="Are you there?")
            )

        assert not get_current_span().is_recording()
        assert responses

        final_answers = []
        for response in responses:
            final_answers.append(response)

        assert len(final_answers) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionManyResponses"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert client_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionManyResponses"
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "stream"
        assert not client_span.data["rpc"]["error"]

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_streaming_many_to_many(self) -> None:
        with tracer.start_as_current_span("test"):
            responses = self.server_stub.ManyQuestionsManyReponses(
                self.generate_questions()
            )

        assert not get_current_span().is_recording()
        assert responses

        final_answers = []
        for response in responses:
            final_answers.append(response)

        assert len(final_answers) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/ManyQuestionsManyReponses"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert client_span.data["rpc"]["call"] == "/stan.Stan/ManyQuestionsManyReponses"
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "stream"
        assert not client_span.data["rpc"]["error"]

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_unary_one_to_one_with_call(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.server_stub.OneQuestionOneResponse.with_call(
                stan_pb2.QuestionRequest(question="Are you there?")
            )

        assert not get_current_span().is_recording()
        assert response
        assert isinstance(response, tuple)
        assert (
            response[0].answer
            == "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka"
        )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneResponse"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert client_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneResponse"
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "unary"
        assert not client_span.data["rpc"]["error"]

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_streaming_many_to_one_with_call(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.server_stub.ManyQuestionsOneResponse.with_call(
                self.generate_questions()
            )

        assert not get_current_span().is_recording()
        assert response

        assert response[0].answer == "Ok"
        assert response[0].was_answered

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/ManyQuestionsOneResponse"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert client_span.data["rpc"]["call"] == "/stan.Stan/ManyQuestionsOneResponse"
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "stream"
        assert not client_span.data["rpc"]["error"]

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_async_unary(self) -> None:
        def process_response(future):
            result = future.result()
            assert isinstance(result, stan_pb2.QuestionResponse)
            assert result.was_answered
            assert (
                result.answer
                == "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka"
            )

        with tracer.start_as_current_span("test"):
            future = self.server_stub.OneQuestionOneResponse.future(
                stan_pb2.QuestionRequest(question="Are you there?")
            )
            future.add_done_callback(process_response)
            time.sleep(0.7)

        assert not get_current_span().is_recording()
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneResponse"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert client_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneResponse"
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "unary"
        assert not client_span.data["rpc"]["error"]

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_async_stream(self) -> None:
        def process_response(future):
            result = future.result()
            assert isinstance(result, stan_pb2.QuestionResponse)
            assert result.was_answered
            assert result.answer == "Ok"

        with tracer.start_as_current_span("test"):
            future = self.server_stub.ManyQuestionsOneResponse.future(
                self.generate_questions()
            )
            future.add_done_callback(process_response)

        # The question generator delays at random intervals between questions so to assure that
        # all questions are sent and processed before we start testing the results.
        time.sleep(5)

        assert not get_current_span().is_recording()
        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not client_span.ec
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/ManyQuestionsOneResponse"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert client_span.data["rpc"]["call"] == "/stan.Stan/ManyQuestionsOneResponse"
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "stream"
        assert not client_span.data["rpc"]["error"]

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_server_error(self) -> None:
        response = None
        with tracer.start_as_current_span("test"):
            try:
                response = self.server_stub.OneQuestionOneErrorResponse(
                    stan_pb2.QuestionRequest(question="Do u error?")
                )
            except Exception:
                pass

        assert not get_current_span().is_recording()
        assert not response

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        log_span = get_first_span_by_name(spans, "log")
        server_span = get_first_span_by_name(spans, "rpc-server")
        client_span = get_first_span_by_name(spans, "rpc-client")
        test_span = get_first_span_by_name(spans, "sdk")

        assert log_span
        assert server_span
        assert client_span
        assert test_span

        # Same traceId
        assert server_span.t == client_span.t
        assert server_span.t == test_span.t

        # Parent relationships
        assert server_span.p == client_span.s
        assert client_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert client_span.ec == 1
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert (
            server_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneErrorResponse"
        )
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

        # rpc-client
        assert client_span.n == "rpc-client"
        assert client_span.k is SpanKind.CLIENT
        assert client_span.stack
        assert client_span.data["rpc"]["flavor"] == "grpc"
        assert (
            client_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneErrorResponse"
        )
        assert client_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert client_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert client_span.data["rpc"]["call_type"] == "unary"
        assert client_span.data["rpc"]["error"]

        # log
        assert log_span.n == "log"
        assert log_span.data["log"]
        assert (
            log_span.data["log"]["message"]
            == "Exception calling application: Simulated error"
        )

        # test-span
        assert test_span.n == "sdk"
        assert test_span.data["sdk"]["name"] == "test"

    def test_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True

        response = self.server_stub.OneQuestionOneResponse.with_call(
            stan_pb2.QuestionRequest(question="Are you there?")
        )
        assert (
            response[0].answer
            == "Invention, my dear friends, is 93% perspiration, 6% electricity, 4% evaporation, and 2% butterscotch ripple. – Willy Wonka"
        )

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        server_span = spans[0]

        assert server_span

        # Parent relationships
        assert not server_span.p

        # Error logging
        assert not server_span.ec

        # rpc-server
        assert server_span.n == "rpc-server"
        assert server_span.k is SpanKind.SERVER
        assert not server_span.stack
        assert server_span.data["rpc"]["flavor"] == "grpc"
        assert server_span.data["rpc"]["call"] == "/stan.Stan/OneQuestionOneResponse"
        assert server_span.data["rpc"]["host"] == testenv["grpc_host"]
        assert server_span.data["rpc"]["port"] == str(testenv["grpc_port"])
        assert not server_span.data["rpc"]["error"]

    def test_no_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = False
        responses = self.server_stub.OneQuestionManyResponses(
            stan_pb2.QuestionRequest(question="Are you there?")
        )

        assert responses

        spans = self.recorder.queued_spans()
        assert len(spans) == 0
