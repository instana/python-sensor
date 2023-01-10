# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import os
import logging
import unittest

from instana.agent.host import HostAgent
from instana.tracer import InstanaTracer
from instana.options import StandardOptions
from instana.recorder import StanRecorder
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestHost(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestHost, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        pass

    def tearDown(self):
        """ Reset all environment variables of consequence """
        variable_names = (
                "AWS_EXECUTION_ENV", "INSTANA_EXTRA_HTTP_HEADERS",
                "INSTANA_ENDPOINT_URL", "INSTANA_ENDPOINT_PROXY",
                "INSTANA_AGENT_KEY", "INSTANA_LOG_LEVEL",
                "INSTANA_SERVICE_NAME", "INSTANA_SECRETS", "INSTANA_TAGS",
                )

        for variable_name in variable_names:
            if variable_name in os.environ:
                os.environ.pop(variable_name)

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = HostAgent()
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_secrets(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent.options, 'secrets_matcher'))
        self.assertEqual(self.agent.options.secrets_matcher, 'contains-ignore-case')
        self.assertTrue(hasattr(self.agent.options, 'secrets_list'))
        self.assertEqual(self.agent.options.secrets_list, ['key', 'pass', 'secret'])

    def test_options_have_extra_http_headers(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(hasattr(self.agent.options, 'extra_http_headers'))

    def test_has_options(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(isinstance(self.agent.options, StandardOptions))

    def test_agent_default_log_level(self):
        self.create_agent_and_setup_tracer()
        self.assertEqual(self.agent.options.log_level, logging.WARNING)

    def test_agent_instana_debug(self):
        os.environ['INSTANA_DEBUG'] = "asdf"
        self.create_agent_and_setup_tracer()
        self.assertEqual(self.agent.options.log_level, logging.DEBUG)

    def test_agent_instana_service_name(self):
        os.environ['INSTANA_SERVICE_NAME'] = "greycake"
        self.create_agent_and_setup_tracer()
        self.assertEqual(self.agent.options.service_name, "greycake")
