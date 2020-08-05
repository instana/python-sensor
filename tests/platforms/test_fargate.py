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
        if "INSTANA_ENDPOINT_PROXY" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_PROXY")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")
        if "INSTANA_SECRETS" in os.environ:
            os.environ.pop("INSTANA_SECRETS")
        if "INSTANA_TAGS" in os.environ:
            os.environ.pop("INSTANA_TAGS")

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = AWSFargateAgent()
        self.span_recorder = AWSFargateRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_has_options(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(type(self.agent.options) is AWSFargateOptions)

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

    def test_default_secrets(self):
        self.create_agent_and_setup_tracer()
        self.assertIsNone(self.agent.options.secrets)
        self.assertTrue(hasattr(self.agent.options, 'secrets_matcher'))
        self.assertEqual(self.agent.options.secrets_matcher, 'contains-ignore-case')
        self.assertTrue(hasattr(self.agent.options, 'secrets_list'))
        self.assertEqual(self.agent.options.secrets_list, ['key', 'pass', 'secret'])

    def test_custom_secrets(self):
        os.environ["INSTANA_SECRETS"] = "equals:love,war,games"
        self.create_agent_and_setup_tracer()

        self.assertTrue(hasattr(self.agent.options, 'secrets_matcher'))
        self.assertEqual(self.agent.options.secrets_matcher, 'equals')
        self.assertTrue(hasattr(self.agent.options, 'secrets_list'))
        self.assertEqual(self.agent.options.secrets_list, ['love', 'war', 'games'])

    def test_default_tags(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent.options, 'tags'))
        self.assertIsNone(self.agent.options.tags)

    def test_custom_tags(self):
        os.environ["INSTANA_TAGS"] = "love,war,games"
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent.options, 'tags'))
        self.assertEqual(self.agent.options.tags, ["love", "war", "games"])

        payload = self.agent.collector.prepare_payload()

        assert(payload)
        host_plugin = None
        plugins = payload['metrics']['plugins']
        for plugin in plugins:
            if plugin["name"] == "com.instana.plugin.host":
                host_plugin = plugin
        assert(host_plugin)
        assert(host_plugin["entityId"] == "h")
        assert(host_plugin["data"]["tags"] == ['love', 'war', 'games'])

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

    def test_custom_proxy(self):
        os.environ["INSTANA_ENDPOINT_PROXY"] = "http://myproxy.123"
        self.create_agent_and_setup_tracer()
        assert(self.agent.options.endpoint_proxy == { 'https': "http://myproxy.123" })