# (c) Copyright IBM Corp. 2024

import os
import logging
import unittest

from instana.tracer import InstanaTracer
from instana.options import EKSFargateOptions
from instana.recorder import StanRecorder
from instana.agent.aws_eks_fargate import EKSFargateAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestFargate(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestFargate, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        os.environ["INSTANA_TRACER_ENVIRONMENT"] = "AWS_EKS_FARGATE"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

    def tearDown(self):
        """ Reset all environment variables of consequence """
        variable_names = (
                "INSTANA_TRACER_ENVIRONMENT",
                "AWS_EXECUTION_ENV", "INSTANA_EXTRA_HTTP_HEADERS",
                "INSTANA_ENDPOINT_URL", "INSTANA_ENDPOINT_PROXY",
                "INSTANA_AGENT_KEY", "INSTANA_LOG_LEVEL",
                "INSTANA_SECRETS", "INSTANA_DEBUG", "INSTANA_TAGS"
                )

        for variable_name in variable_names:
            if variable_name in os.environ:
                os.environ.pop(variable_name)

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = EKSFargateAgent()
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_has_options(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(isinstance(self.agent.options, EKSFargateOptions))

    def test_missing_variables(self):
        with self.assertLogs("instana", level=logging.WARN) as context:
            os.environ.pop("INSTANA_ENDPOINT_URL")
            agent = EKSFargateAgent()
            self.assertFalse(agent.can_send())
            self.assertIsNone(agent.collector)
        self.assertIn('environment variables not set', context.output[0])

        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        with self.assertLogs("instana", level=logging.WARN) as context:
            os.environ.pop("INSTANA_AGENT_KEY")
            agent = EKSFargateAgent()
            self.assertFalse(agent.can_send())
            self.assertIsNone(agent.collector)
        self.assertIn('environment variables not set', context.output[0])

    def test_default_secrets(self):
        self.create_agent_and_setup_tracer()
        self.assertIsNone(self.agent.options.secrets)
        self.assertTrue(hasattr(self.agent.options, 'secrets_matcher'))
        self.assertEqual(self.agent.options.secrets_matcher, 'contains-ignore-case')
        self.assertTrue(hasattr(self.agent.options, 'secrets_list'))
        self.assertListEqual(self.agent.options.secrets_list, ['key', 'pass', 'secret'])

    def test_custom_secrets(self):
        os.environ["INSTANA_SECRETS"] = "equals:love,war,games"
        self.create_agent_and_setup_tracer()

        self.assertTrue(hasattr(self.agent.options, 'secrets_matcher'))
        self.assertEqual(self.agent.options.secrets_matcher, 'equals')
        self.assertTrue(hasattr(self.agent.options, 'secrets_list'))
        self.assertListEqual(self.agent.options.secrets_list, ['love', 'war', 'games'])

    def test_default_tags(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent.options, 'tags'))
        self.assertIsNone(self.agent.options.tags)

    def test_has_extra_http_headers(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(hasattr(self.agent.options, 'extra_http_headers'))

    def test_agent_extra_http_headers(self):
        os.environ['INSTANA_EXTRA_HTTP_HEADERS'] = "X-Test-Header;X-Another-Header;X-And-Another-Header"
        self.create_agent_and_setup_tracer()
        self.assertIsNotNone(self.agent.options.extra_http_headers)
        should_headers = ['x-test-header', 'x-another-header', 'x-and-another-header']
        self.assertListEqual(should_headers, self.agent.options.extra_http_headers)

    def test_agent_default_log_level(self):
        self.create_agent_and_setup_tracer()
        self.assertEqual(self.agent.options.log_level, logging.WARNING)

    def test_agent_custom_log_level(self):
        os.environ['INSTANA_LOG_LEVEL'] = "eRror"
        self.create_agent_and_setup_tracer()
        self.assertEqual(self.agent.options.log_level, logging.ERROR)

    def test_custom_proxy(self):
        os.environ["INSTANA_ENDPOINT_PROXY"] = "http://myproxy.123"
        self.create_agent_and_setup_tracer()
        self.assertDictEqual(self.agent.options.endpoint_proxy, {'https': "http://myproxy.123"})
