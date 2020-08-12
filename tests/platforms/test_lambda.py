from __future__ import absolute_import

import os
import sys
import json
import wrapt
import logging
import unittest

from instana.tracer import InstanaTracer
from instana.agent.aws_lambda import AWSLambdaAgent
from instana.options import AWSLambdaOptions
from instana.recorder import StanRecorder
from instana import lambda_handler
from instana import get_lambda_handler_or_default
from instana.instrumentation.aws.lambda_inst import lambda_handler_with_instana
from instana.instrumentation.aws.triggers import read_http_query_params
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer
from instana.util import normalize_aws_lambda_arn


# Mock Context object
class MockContext(dict):
    def __init__(self, **kwargs):
        super(MockContext, self).__init__(**kwargs)
        self.invoked_function_arn = "arn:aws:lambda:us-east-2:12345:function:TestPython:1"
        self.function_name = "TestPython"
        self.function_version = "1"


# This is the target handler that will be instrumented for these tests
def my_lambda_handler(event, context):
    # print("target_handler called")
    return "All Ok"

# We only want to monkey patch the test handler once so do it here
os.environ["LAMBDA_HANDLER"] = "tests.platforms.test_lambda.my_lambda_handler"
module_name, function_name = get_lambda_handler_or_default()
wrapt.wrap_function_wrapper(module_name, function_name, lambda_handler_with_instana)


class TestLambda(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestLambda, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None
        self.pwd = os.path.dirname(os.path.realpath(__file__))

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        os.environ["AWS_EXECUTION_ENV"] = "AWS_Lambda_python_3.8"
        os.environ["LAMBDA_HANDLER"] = "tests.platforms.test_lambda.my_lambda_handler"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"
        self.context = MockContext()

    def tearDown(self):
        """ Reset all environment variables of consequence """
        if "AWS_EXECUTION_ENV" in os.environ:
            os.environ.pop("AWS_EXECUTION_ENV")
        if "LAMBDA_HANDLER" in os.environ:
            os.environ.pop("LAMBDA_HANDLER")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_ENDPOINT_PROXY" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_PROXY")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")
        if "INSTANA_SERVICE_NAME" in os.environ:
            os.environ.pop("INSTANA_SERVICE_NAME")
        if "INSTANA_DEBUG" in os.environ:
            os.environ.pop("INSTANA_DEBUG")
        if "INSTANA_LOG_LEVEL" in os.environ:
            os.environ.pop("INSTANA_LOG_LEVEL")

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = AWSLambdaAgent()
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_invalid_options(self):
        # None of the required env vars are available...
        if "LAMBDA_HANDLER" in os.environ:
            os.environ.pop("LAMBDA_HANDLER")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

        agent = AWSLambdaAgent()
        self.assertFalse(agent._can_send)
        self.assertIsNone(agent.collector)

    def test_secrets(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent.options, 'secrets_matcher'))
        self.assertEqual(self.agent.options.secrets_matcher, 'contains-ignore-case')
        self.assertTrue(hasattr(self.agent.options, 'secrets_list'))
        self.assertEqual(self.agent.options.secrets_list, ['key', 'pass', 'secret'])

    def test_has_extra_http_headers(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(hasattr(self.agent.options, 'extra_http_headers'))

    def test_has_options(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(type(self.agent.options) is AWSLambdaOptions)
        assert(self.agent.options.endpoint_proxy == { })

    def test_get_handler(self):
        os.environ["LAMBDA_HANDLER"] = "tests.lambda_handler"
        handler_module, handler_function = get_lambda_handler_or_default()

        self.assertEqual("tests", handler_module)
        self.assertEqual("lambda_handler", handler_function)

    def test_get_handler_with_multi_subpackages(self):
        os.environ["LAMBDA_HANDLER"] = "tests.one.two.three.lambda_handler"
        handler_module, handler_function = get_lambda_handler_or_default()

        self.assertEqual("tests.one.two.three", handler_module)
        self.assertEqual("lambda_handler", handler_function)

    def test_get_handler_with_space_in_it(self):
        os.environ["LAMBDA_HANDLER"] = " tests.another_module.lambda_handler"
        handler_module, handler_function = get_lambda_handler_or_default()

        self.assertEqual("tests.another_module", handler_module)
        self.assertEqual("lambda_handler", handler_function)

        os.environ["LAMBDA_HANDLER"] = "tests.another_module.lambda_handler    "
        handler_module, handler_function = get_lambda_handler_or_default()

        self.assertEqual("tests.another_module", handler_module)
        self.assertEqual("lambda_handler", handler_function)

    def test_agent_extra_http_headers(self):
        os.environ['INSTANA_EXTRA_HTTP_HEADERS'] = "X-Test-Header;X-Another-Header;X-And-Another-Header"
        self.create_agent_and_setup_tracer()
        self.assertIsNotNone(self.agent.options.extra_http_headers)
        should_headers = ['x-test-header', 'x-another-header', 'x-and-another-header']
        self.assertEqual(should_headers, self.agent.options.extra_http_headers)

    def test_custom_proxy(self):
        os.environ["INSTANA_ENDPOINT_PROXY"] = "http://myproxy.123"
        self.create_agent_and_setup_tracer()
        assert(self.agent.options.endpoint_proxy == { 'https': "http://myproxy.123" })

    def test_custom_service_name(self):
        os.environ['INSTANA_SERVICE_NAME'] = "Legion"
        with open(self.pwd + '/../data/lambda/api_gateway_event.json', 'r') as json_file:
            event = json.load(json_file)

        self.create_agent_and_setup_tracer()

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)
        os.environ.pop('INSTANA_SERVICE_NAME')

        self.assertEqual('All Ok', result)
        payload = self.agent.collector.prepare_payload()

        self.assertTrue("metrics" in payload)
        self.assertTrue("spans" in payload)
        self.assertEqual(2, len(payload.keys()))

        self.assertTrue(type(payload['metrics']['plugins']) is list)
        self.assertTrue(len(payload['metrics']['plugins']) == 1)
        plugin_data = payload['metrics']['plugins'][0]

        self.assertEqual('com.instana.plugin.aws.lambda', plugin_data['name'])
        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', plugin_data['entityId'])

        self.assertEqual(1, len(payload['spans']))

        span = payload['spans'][0]
        self.assertEqual('aws.lambda.entry', span.n)
        self.assertEqual('d5cb361b256413a9', span.t)
        self.assertIsNotNone(span.s)
        self.assertEqual('0901d8ae4fbf1529', span.p)
        self.assertIsNotNone(span.ts)
        self.assertIsNotNone(span.d)

        self.assertEqual({'hl': True, 'cp': 'aws', 'e': 'arn:aws:lambda:us-east-2:12345:function:TestPython:1'},
                         span.f)

        self.assertTrue(span.sy)

        self.assertIsNone(span.ec)
        self.assertIsNone(span.data['lambda']['error'])

        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', span.data['lambda']['arn'])
        self.assertEqual(None, span.data['lambda']['alias'])
        self.assertEqual('python', span.data['lambda']['runtime'])
        self.assertEqual('TestPython', span.data['lambda']['functionName'])
        self.assertEqual('1', span.data['lambda']['functionVersion'])

        self.assertEqual('Legion', span.data['service'])

        self.assertEqual('aws:api.gateway', span.data['lambda']['trigger'])
        self.assertEqual('POST', span.data['http']['method'])
        self.assertEqual('/path/to/resource', span.data['http']['url'])
        self.assertEqual('/{proxy+}', span.data['http']['path_tpl'])
        if sys.version[:3] == '2.7':
            self.assertEqual(u"foo=[u'bar']", span.data['http']['params'])
        else:
            self.assertEqual("foo=['bar']", span.data['http']['params'])

    def test_api_gateway_trigger_tracing(self):
        with open(self.pwd + '/../data/lambda/api_gateway_event.json', 'r') as json_file:
            event = json.load(json_file)

        self.create_agent_and_setup_tracer()

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        self.assertEqual('All Ok', result)
        payload = self.agent.collector.prepare_payload()

        self.assertTrue("metrics" in payload)
        self.assertTrue("spans" in payload)
        self.assertEqual(2, len(payload.keys()))

        self.assertTrue(type(payload['metrics']['plugins']) is list)
        self.assertTrue(len(payload['metrics']['plugins']) == 1)
        plugin_data = payload['metrics']['plugins'][0]

        self.assertEqual('com.instana.plugin.aws.lambda', plugin_data['name'])
        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', plugin_data['entityId'])

        self.assertEqual(1, len(payload['spans']))

        span = payload['spans'][0]
        self.assertEqual('aws.lambda.entry', span.n)
        self.assertEqual('d5cb361b256413a9', span.t)
        self.assertIsNotNone(span.s)
        self.assertEqual('0901d8ae4fbf1529', span.p)
        self.assertIsNotNone(span.ts)
        self.assertIsNotNone(span.d)

        self.assertEqual({'hl': True, 'cp': 'aws', 'e': 'arn:aws:lambda:us-east-2:12345:function:TestPython:1'},
                         span.f)

        self.assertTrue(span.sy)

        self.assertIsNone(span.ec)
        self.assertIsNone(span.data['lambda']['error'])

        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', span.data['lambda']['arn'])
        self.assertEqual(None, span.data['lambda']['alias'])
        self.assertEqual('python', span.data['lambda']['runtime'])
        self.assertEqual('TestPython', span.data['lambda']['functionName'])
        self.assertEqual('1', span.data['lambda']['functionVersion'])
        self.assertIsNone(span.data['service'])

        self.assertEqual('aws:api.gateway', span.data['lambda']['trigger'])
        self.assertEqual('POST', span.data['http']['method'])
        self.assertEqual('/path/to/resource', span.data['http']['url'])
        self.assertEqual('/{proxy+}', span.data['http']['path_tpl'])
        if sys.version[:3] == '2.7':
            self.assertEqual(u"foo=[u'bar']", span.data['http']['params'])
        else:
            self.assertEqual("foo=['bar']", span.data['http']['params'])

    def test_application_lb_trigger_tracing(self):
        with open(self.pwd + '/../data/lambda/api_gateway_event.json', 'r') as json_file:
            event = json.load(json_file)

        self.create_agent_and_setup_tracer()

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        self.assertEqual('All Ok', result)
        payload = self.agent.collector.prepare_payload()

        self.assertTrue("metrics" in payload)
        self.assertTrue("spans" in payload)
        self.assertEqual(2, len(payload.keys()))

        self.assertTrue(type(payload['metrics']['plugins']) is list)
        self.assertTrue(len(payload['metrics']['plugins']) == 1)
        plugin_data = payload['metrics']['plugins'][0]

        self.assertEqual('com.instana.plugin.aws.lambda', plugin_data['name'])
        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', plugin_data['entityId'])

        self.assertEqual(1, len(payload['spans']))

        span = payload['spans'][0]
        self.assertEqual('aws.lambda.entry', span.n)
        self.assertEqual('d5cb361b256413a9', span.t)
        self.assertIsNotNone(span.s)
        self.assertEqual('0901d8ae4fbf1529', span.p)
        self.assertIsNotNone(span.ts)
        self.assertIsNotNone(span.d)

        self.assertEqual({'hl': True, 'cp': 'aws', 'e': 'arn:aws:lambda:us-east-2:12345:function:TestPython:1'},
                         span.f)

        self.assertTrue(span.sy)

        self.assertIsNone(span.ec)
        self.assertIsNone(span.data['lambda']['error'])

        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', span.data['lambda']['arn'])
        self.assertEqual(None, span.data['lambda']['alias'])
        self.assertEqual('python', span.data['lambda']['runtime'])
        self.assertEqual('TestPython', span.data['lambda']['functionName'])
        self.assertEqual('1', span.data['lambda']['functionVersion'])
        self.assertIsNone(span.data['service'])

        self.assertEqual('aws:api.gateway', span.data['lambda']['trigger'])
        self.assertEqual('POST', span.data['http']['method'])
        self.assertEqual('/path/to/resource', span.data['http']['url'])
        if sys.version[:3] == '2.7':
            self.assertEqual(u"foo=[u'bar']", span.data['http']['params'])
        else:
            self.assertEqual("foo=['bar']", span.data['http']['params'])

    def test_cloudwatch_trigger_tracing(self):
        with open(self.pwd + '/../data/lambda/cloudwatch_event.json', 'r') as json_file:
            event = json.load(json_file)

        self.create_agent_and_setup_tracer()

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        self.assertEqual('All Ok', result)
        payload = self.agent.collector.prepare_payload()

        self.assertTrue("metrics" in payload)
        self.assertTrue("spans" in payload)
        self.assertEqual(2, len(payload.keys()))

        self.assertTrue(type(payload['metrics']['plugins']) is list)
        self.assertTrue(len(payload['metrics']['plugins']) == 1)
        plugin_data = payload['metrics']['plugins'][0]

        self.assertEqual('com.instana.plugin.aws.lambda', plugin_data['name'])
        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', plugin_data['entityId'])

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

        self.assertIsNone(span.sy)

        self.assertIsNone(span.ec)
        self.assertIsNone(span.data['lambda']['error'])

        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', span.data['lambda']['arn'])
        self.assertEqual(None, span.data['lambda']['alias'])
        self.assertEqual('python', span.data['lambda']['runtime'])
        self.assertEqual('TestPython', span.data['lambda']['functionName'])
        self.assertEqual('1', span.data['lambda']['functionVersion'])
        self.assertIsNone(span.data['service'])

        self.assertEqual('aws:cloudwatch.events', span.data['lambda']['trigger'])
        self.assertEqual('cdc73f9d-aea9-11e3-9d5a-835b769c0d9c', span.data["lambda"]["cw"]["events"]["id"])
        self.assertEqual(False, span.data["lambda"]["cw"]["events"]["more"])
        self.assertTrue(type(span.data["lambda"]["cw"]["events"]["resources"]) is list)
        self.assertEqual(1, len(span.data["lambda"]["cw"]["events"]["resources"]))
        self.assertEqual('arn:aws:events:eu-west-1:123456789012:rule/ExampleRule',
                         span.data["lambda"]["cw"]["events"]["resources"][0])

    def test_cloudwatch_logs_trigger_tracing(self):
        with open(self.pwd + '/../data/lambda/cloudwatch_logs_event.json', 'r') as json_file:
            event = json.load(json_file)

        self.create_agent_and_setup_tracer()

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        self.assertEqual('All Ok', result)
        payload = self.agent.collector.prepare_payload()

        self.assertTrue("metrics" in payload)
        self.assertTrue("spans" in payload)
        self.assertEqual(2, len(payload.keys()))

        self.assertTrue(type(payload['metrics']['plugins']) is list)
        self.assertTrue(len(payload['metrics']['plugins']) == 1)
        plugin_data = payload['metrics']['plugins'][0]

        self.assertEqual('com.instana.plugin.aws.lambda', plugin_data['name'])
        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', plugin_data['entityId'])

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

        self.assertIsNone(span.sy)

        self.assertIsNone(span.ec)
        self.assertIsNone(span.data['lambda']['error'])

        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', span.data['lambda']['arn'])
        self.assertEqual(None, span.data['lambda']['alias'])
        self.assertEqual('python', span.data['lambda']['runtime'])
        self.assertEqual('TestPython', span.data['lambda']['functionName'])
        self.assertEqual('1', span.data['lambda']['functionVersion'])
        self.assertIsNone(span.data['service'])

        self.assertEqual('aws:cloudwatch.logs', span.data['lambda']['trigger'])
        self.assertFalse("decodingError" in span.data['lambda']['cw']['logs'])
        self.assertEqual('testLogGroup', span.data['lambda']['cw']['logs']['group'])
        self.assertEqual('testLogStream', span.data['lambda']['cw']['logs']['stream'])
        self.assertEqual(None, span.data['lambda']['cw']['logs']['more'])
        self.assertTrue(type(span.data['lambda']['cw']['logs']['events']) is list)
        self.assertEqual(2, len(span.data['lambda']['cw']['logs']['events']))
        self.assertEqual('[ERROR] First test message', span.data['lambda']['cw']['logs']['events'][0])
        self.assertEqual('[ERROR] Second test message', span.data['lambda']['cw']['logs']['events'][1])

    def test_s3_trigger_tracing(self):
        with open(self.pwd + '/../data/lambda/s3_event.json', 'r') as json_file:
            event = json.load(json_file)

        self.create_agent_and_setup_tracer()

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        self.assertEqual('All Ok', result)
        payload = self.agent.collector.prepare_payload()

        self.assertTrue("metrics" in payload)
        self.assertTrue("spans" in payload)
        self.assertEqual(2, len(payload.keys()))

        self.assertTrue(type(payload['metrics']['plugins']) is list)
        self.assertTrue(len(payload['metrics']['plugins']) == 1)
        plugin_data = payload['metrics']['plugins'][0]

        self.assertEqual('com.instana.plugin.aws.lambda', plugin_data['name'])
        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', plugin_data['entityId'])

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

        self.assertIsNone(span.sy)

        self.assertIsNone(span.ec)
        self.assertIsNone(span.data['lambda']['error'])

        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', span.data['lambda']['arn'])
        self.assertEqual(None, span.data['lambda']['alias'])
        self.assertEqual('python', span.data['lambda']['runtime'])
        self.assertEqual('TestPython', span.data['lambda']['functionName'])
        self.assertEqual('1', span.data['lambda']['functionVersion'])
        self.assertIsNone(span.data['service'])

        self.assertEqual('aws:s3', span.data['lambda']['trigger'])
        self.assertTrue(type(span.data["lambda"]["s3"]["events"]) is list)
        events = span.data["lambda"]["s3"]["events"]
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual('ObjectCreated:Put', event['event'])
        self.assertEqual('example-bucket', event['bucket'])
        self.assertEqual('test/key', event['object'])

    def test_sqs_trigger_tracing(self):
        with open(self.pwd + '/../data/lambda/sqs_event.json', 'r') as json_file:
            event = json.load(json_file)

        self.create_agent_and_setup_tracer()

        # Call the Instana Lambda Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Lambda Handler and execute it.
        # The original Lambda handler is set in os.environ["LAMBDA_HANDLER"]
        result = lambda_handler(event, self.context)

        self.assertEqual('All Ok', result)
        payload = self.agent.collector.prepare_payload()

        self.assertTrue("metrics" in payload)
        self.assertTrue("spans" in payload)
        self.assertEqual(2, len(payload.keys()))

        self.assertTrue(type(payload['metrics']['plugins']) is list)
        self.assertTrue(len(payload['metrics']['plugins']) == 1)
        plugin_data = payload['metrics']['plugins'][0]

        self.assertEqual('com.instana.plugin.aws.lambda', plugin_data['name'])
        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', plugin_data['entityId'])

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

        self.assertIsNone(span.sy)

        self.assertIsNone(span.ec)
        self.assertIsNone(span.data['lambda']['error'])

        self.assertEqual('arn:aws:lambda:us-east-2:12345:function:TestPython:1', span.data['lambda']['arn'])
        self.assertEqual(None, span.data['lambda']['alias'])
        self.assertEqual('python', span.data['lambda']['runtime'])
        self.assertEqual('TestPython', span.data['lambda']['functionName'])
        self.assertEqual('1', span.data['lambda']['functionVersion'])
        self.assertIsNone(span.data['service'])

        self.assertEqual('aws:sqs', span.data['lambda']['trigger'])
        self.assertTrue(type(span.data["lambda"]["sqs"]["messages"]) is list)
        messages = span.data["lambda"]["sqs"]["messages"]
        self.assertEqual(1, len(messages))
        message = messages[0]
        self.assertEqual('arn:aws:sqs:us-west-1:123456789012:MyQueue', message['queue'])

    def test_read_query_params(self):
        event = { "queryStringParameters": {"foo": "bar" },
                  "multiValueQueryStringParameters": { "foo": ["bar"] } }
        params = read_http_query_params(event)
        self.assertEqual("foo=['bar']", params)

    def test_read_query_params_with_none_data(self):
        event = { "queryStringParameters": None,
                  "multiValueQueryStringParameters": None }
        params = read_http_query_params(event)
        self.assertEqual("", params)

    def test_read_query_params_with_bad_event(self):
        event = None
        params = read_http_query_params(event)
        self.assertEqual("", params)

    def test_arn_parsing(self):
        ctx = MockContext()

        assert(normalize_aws_lambda_arn(ctx) == "arn:aws:lambda:us-east-2:12345:function:TestPython:1")

        # Without version should return a fully qualified ARN (with version)
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-2:12345:function:TestPython"
        assert(normalize_aws_lambda_arn(ctx) == "arn:aws:lambda:us-east-2:12345:function:TestPython:1")

        # Fully qualified already with the '$LATEST' special tag
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-2:12345:function:TestPython:$LATEST"
        assert(normalize_aws_lambda_arn(ctx) == "arn:aws:lambda:us-east-2:12345:function:TestPython:$LATEST")

    def test_agent_default_log_level(self):
        self.create_agent_and_setup_tracer()
        assert self.agent.options.log_level == logging.WARNING

    def test_agent_custom_log_level(self):
        os.environ['INSTANA_LOG_LEVEL'] = "eRror"
        self.create_agent_and_setup_tracer()
        assert self.agent.options.log_level == logging.ERROR
