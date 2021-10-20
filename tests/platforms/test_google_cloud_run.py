# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from __future__ import absolute_import

import os
import logging
import unittest

from instana.tracer import InstanaTracer
from instana.options import GCROptions
from instana.recorder import StanRecorder
from instana.agent.google_cloud_run import GCRAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestGCR(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestGCR, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        os.environ["K_SERVICE"] = "service"
        os.environ["K_CONFIGURATION"] = "configuration"
        os.environ["K_REVISION"] = "revision"
        os.environ["PORT"] = "port"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

    def tearDown(self):
        """ Reset all environment variables of consequence """
        if "K_SERVICE" in os.environ:
            os.environ.pop("K_SERVICE")
        if "K_CONFIGURATION" in os.environ:
            os.environ.pop("K_CONFIGURATION")
        if "K_REVISION" in os.environ:
            os.environ.pop("K_REVISION")
        if "PORT" in os.environ:
            os.environ.pop("PORT")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_ENDPOINT_PROXY" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_PROXY")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")
        if "INSTANA_LOG_LEVEL" in os.environ:
            os.environ.pop("INSTANA_LOG_LEVEL")
        if "INSTANA_SECRETS" in os.environ:
            os.environ.pop("INSTANA_SECRETS")
        if "INSTANA_DEBUG" in os.environ:
            os.environ.pop("INSTANA_DEBUG")
        if "INSTANA_TAGS" in os.environ:
            os.environ.pop("INSTANA_TAGS")

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = GCRAgent(service="service", configuration="configuration", revision="revision")
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_has_options(self):
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent, 'options'))
        self.assertTrue(isinstance(self.agent.options, GCROptions))

    def test_invalid_options(self):
        # None of the required env vars are available...
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

        agent = GCRAgent(service="service", configuration="configuration", revision="revision")
        self.assertFalse(agent.can_send())
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

    def test_agent_default_log_level(self):
        self.create_agent_and_setup_tracer()
        assert self.agent.options.log_level == logging.WARNING

    def test_agent_custom_log_level(self):
        os.environ['INSTANA_LOG_LEVEL'] = "eRror"
        self.create_agent_and_setup_tracer()
        assert self.agent.options.log_level == logging.ERROR

    def test_custom_proxy(self):
        os.environ["INSTANA_ENDPOINT_PROXY"] = "http://myproxy.123"
        self.create_agent_and_setup_tracer()
        assert self.agent.options.endpoint_proxy == {'https': "http://myproxy.123"}
