from __future__ import absolute_import

import os
import wrapt
import unittest
from instana.singletons import set_agent, set_tracer
from instana.tracer import InstanaTracer
from instana.agent import AWSLambdaAgent
from instana.recorder import AWSLambdaRecorder
from instana import lambda_handler
from instana import get_lambda_handler_or_default
from instana.instrumentation.aws_lambda import lambda_handler_with_instana


# Mock Context object
class TestContext(dict):
    def __init__(self, **kwargs):
        super(TestContext, self).__init__(**kwargs)
        self.invoked_function_arn = "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        self.function_name = "TestPython"
        self.function_version = "1"


# This is the target handler that will be instrumented for these tests
def test_lambda_handler(event, context):
    print("target_handler called")
    return "All Ok"


class TestLambda(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestLambda, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None

    def tearDown(self):
        """ Reset all environment variables of consequence """
        if "LAMBDA_HANDLER" in os.environ:
            os.environ.pop("LAMBDA_HANDLER")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

    def create_agent_and_setup_tracer(self):
        self.agent = AWSLambdaAgent()
        self.span_recorder = AWSLambdaRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_invalid_options(self):
        # None of the required env vars are available...
        agent = AWSLambdaAgent()
        self.assertFalse(agent._can_send)
        self.assertIsNone(agent.collector)

    def test_get_handler(self):
        os.environ["LAMBDA_HANDLER"] = "tests.lambda_handler"
        handler_module, handler_function = get_lambda_handler_or_default()

        self.assertEqual("tests", handler_module)
        self.assertEqual("lambda_handler", handler_function)

    def test_agent_extra_headers(self):
        os.environ['INSTANA_EXTRA_HTTP_HEADERS'] = "X-Test-Header;X-Another-Header;X-And-Another-Header"
        self.create_agent_and_setup_tracer()
        self.assertIsNotNone(self.agent.extra_headers)
        should_headers = ['x-test-header', 'x-another-header', 'x-and-another-header']
        self.assertEqual(should_headers, self.agent.extra_headers)

    def test_api_gateway_tracing(self):
        os.environ["LAMBDA_HANDLER"] = "tests.test_lambda.test_lambda_handler"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

        self.create_agent_and_setup_tracer()

        module_name, function_name = get_lambda_handler_or_default()
        self.assertEqual("tests.test_lambda", module_name)
        self.assertEqual("test_lambda_handler", function_name)

        wrapt.wrap_function_wrapper(module_name, function_name, lambda_handler_with_instana)

        event = dict()
        context = TestContext()
        result = lambda_handler(event, context)

        self.assertEqual('All Ok', result)
        payload = self.agent.collector.prepare_payload()

        self.assertTrue("metrics" in payload)
        self.assertTrue("spans" in payload)
        self.assertEqual(2, len(payload.keys()))
        self.assertEqual('com.instana.plugin.aws.lambda', payload['metrics']['plugins']['name'])
        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', payload['metrics']['plugins']['entityId'])

        self.assertEqual(1, len(payload['spans']))

        span = payload['spans'][0]
        self.assertEqual('aws.lambda.entry', span.n)
        self.assertIsNotNone(span.t)
        self.assertIsNotNone(span.s)
        self.assertIsNone(span.p)
        self.assertIsNotNone(span.ts)
        self.assertIsNotNone(span.d)

        self.assertEqual({'hl': True, 'cp': 'aws', 'e': 'arn:aws:lambda:us-east-2:12345:function:TestPython:1'},
                         span.f)

        self.assertIsNone(span.ec)
        self.assertIsNone(span.error)
        self.assertIsNone(span.data['lambda']['error'])

        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', span.data['lambda']['arn'])
        self.assertEqual(None, span.data['lambda']['alias'])
        self.assertEqual('python', span.data['lambda']['runtime'])
        self.assertEqual('TestPython', span.data['lambda']['functionName'])
        self.assertEqual('1', span.data['lambda']['functionVersion'])


