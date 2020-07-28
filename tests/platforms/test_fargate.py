from __future__ import absolute_import

import os
import sys
import json
import pytest
import unittest

from instana.tracer import InstanaTracer
from instana.options import AWSFargateOptions
from instana.recorder import AWSFargateRecorder
from instana.agent.aws_fargate import AWSFargateAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestFargate(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestFargate, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None
        self.pwd = os.path.dirname(os.path.realpath(__file__))

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        os.environ["AWS_EXECUTION_ENV"] = "AWS_ECS_FARGATE"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

    def tearDown(self):
        """ Reset all environment variables of consequence """
        if "AWS_EXECUTION_ENV" in os.environ:
            os.environ.pop("AWS_EXECUTION_ENV")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = AWSFargateAgent()
        self.span_recorder = AWSFargateRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_invalid_options(self):
        # None of the required env vars are available...
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

        agent = AWSFargateAgent()
        self.assertFalse(agent._can_send)
        self.assertIsNone(agent.collector)

    def test_secrets(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'secrets_matcher'))
        self.assertEqual(self.agent.secrets_matcher, 'contains-ignore-case')
        self.assertTrue(hasattr(self.agent, 'secrets_list'))
        self.assertEqual(self.agent.secrets_list, ['key', 'pass', 'secret'])

    def test_has_options(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(type(self.agent.options) is AWSFargateOptions)

    def test_has_extra_http_headers(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(hasattr(self.agent.options, 'extra_http_headers'))

    def test_agent_extra_http_headers(self):
        os.environ['INSTANA_EXTRA_HTTP_HEADERS'] = "X-Test-Header;X-Another-Header;X-And-Another-Header"
        self.create_agent_and_setup_tracer()
        self.assertIsNotNone(self.agent.options.extra_http_headers)
        should_headers = ['x-test-header', 'x-another-header', 'x-and-another-header']
        self.assertEqual(should_headers, self.agent.options.extra_http_headers)

    @pytest.mark.skip("todo")
    def test_custom_service_name(self):
        os.environ['INSTANA_SERVICE_NAME'] = "Legion"
        with open(self.pwd + '/../data/lambda/api_gateway_event.json', 'r') as json_file:
            event = json.load(json_file)

        self.create_agent_and_setup_tracer()

        # Call the Instana Fargate Handler as we do in the real world.  It will initiate tracing and then
        # figure out the original (the users') Fargate Handler and execute it.
        # The original Fargate handler is set in os.environ["LAMBDA_HANDLER"]
        # result = lambda_handler(event, self.context)
        os.environ.pop('INSTANA_SERVICE_NAME')

        # self.assertEqual('All Ok', result)
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

