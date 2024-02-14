# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import logging
import unittest

from mock import MagicMock, patch
import requests

from instana.agent.host import HostAgent
from instana.fsm import Discovery
from instana.log import logger
from instana.options import StandardOptions
from instana.recorder import StanRecorder
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer
from instana.tracer import InstanaTracer


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

    @patch.object(requests.Session, "put")
    def test_announce_is_successful(self, mock_requests_session_put):
        test_pid = 4242
        test_process_name = 'test_process'
        test_process_args = ['-v', '-d']
        test_agent_uuid = '83bf1e09-ab16-4203-abf5-34ee0977023a'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = (
                '{'
                f'  "pid": {test_pid}, '
                f'  "agentUuid": "{test_agent_uuid}"'
                '}')

        # This mocks the call to self.agent.client.put
        mock_requests_session_put.return_value = mock_response

        self.create_agent_and_setup_tracer()
        d = Discovery(pid=test_pid,
                      name=test_process_name, args=test_process_args)
        payload = self.agent.announce(d)

        self.assertIn('pid', payload)
        self.assertEqual(test_pid, payload['pid'])

        self.assertIn('agentUuid', payload)
        self.assertEqual(test_agent_uuid, payload['agentUuid'])


    @patch.object(requests.Session, "put")
    def test_announce_fails_with_non_200(self, mock_requests_session_put):
        test_pid = 4242
        test_process_name = 'test_process'
        test_process_args = ['-v', '-d']
        test_agent_uuid = '83bf1e09-ab16-4203-abf5-34ee0977023a'

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = ''
        mock_requests_session_put.return_value = mock_response

        self.create_agent_and_setup_tracer()
        d = Discovery(pid=test_pid,
                      name=test_process_name, args=test_process_args)
        with self.assertLogs(logger, level='DEBUG') as log:
            payload = self.agent.announce(d)
        self.assertIsNone(payload)
        self.assertEqual(len(log.output), 1)
        self.assertEqual(len(log.records), 1)
        self.assertIn('response status code', log.output[0])
        self.assertIn('is NOT 200', log.output[0])


    @patch.object(requests.Session, "put")
    def test_announce_fails_with_non_json(self, mock_requests_session_put):
        test_pid = 4242
        test_process_name = 'test_process'
        test_process_args = ['-v', '-d']
        test_agent_uuid = '83bf1e09-ab16-4203-abf5-34ee0977023a'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = ''
        mock_requests_session_put.return_value = mock_response

        self.create_agent_and_setup_tracer()
        d = Discovery(pid=test_pid,
                      name=test_process_name, args=test_process_args)
        with self.assertLogs(logger, level='DEBUG') as log:
            payload = self.agent.announce(d)
        self.assertIsNone(payload)
        self.assertEqual(len(log.output), 1)
        self.assertEqual(len(log.records), 1)
        self.assertIn('response is not JSON', log.output[0])

    @patch.object(requests.Session, "put")
    def test_announce_fails_with_empty_list_json(self, mock_requests_session_put):
        test_pid = 4242
        test_process_name = 'test_process'
        test_process_args = ['-v', '-d']
        test_agent_uuid = '83bf1e09-ab16-4203-abf5-34ee0977023a'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = '[]'
        mock_requests_session_put.return_value = mock_response

        self.create_agent_and_setup_tracer()
        d = Discovery(pid=test_pid,
                      name=test_process_name, args=test_process_args)
        with self.assertLogs(logger, level='DEBUG') as log:
            payload = self.agent.announce(d)
        self.assertIsNone(payload)
        self.assertEqual(len(log.output), 1)
        self.assertEqual(len(log.records), 1)
        self.assertIn('payload has no fields', log.output[0])


    @patch.object(requests.Session, "put")
    def test_announce_fails_with_missing_pid(self, mock_requests_session_put):
        test_pid = 4242
        test_process_name = 'test_process'
        test_process_args = ['-v', '-d']
        test_agent_uuid = '83bf1e09-ab16-4203-abf5-34ee0977023a'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = (
                '{'
                f'  "agentUuid": "{test_agent_uuid}"'
                '}')
        mock_requests_session_put.return_value = mock_response

        self.create_agent_and_setup_tracer()
        d = Discovery(pid=test_pid,
                      name=test_process_name, args=test_process_args)
        with self.assertLogs(logger, level='DEBUG') as log:
            payload = self.agent.announce(d)
        self.assertIsNone(payload)
        self.assertEqual(len(log.output), 1)
        self.assertEqual(len(log.records), 1)
        self.assertIn('response payload has no pid', log.output[0])


    @patch.object(requests.Session, "put")
    def test_announce_fails_with_missing_uuid(self, mock_requests_session_put):
        test_pid = 4242
        test_process_name = 'test_process'
        test_process_args = ['-v', '-d']
        test_agent_uuid = '83bf1e09-ab16-4203-abf5-34ee0977023a'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = (
                '{'
                f'  "pid": {test_pid} '
                '}')
        mock_requests_session_put.return_value = mock_response

        self.create_agent_and_setup_tracer()
        d = Discovery(pid=test_pid,
                      name=test_process_name, args=test_process_args)
        with self.assertLogs(logger, level='DEBUG') as log:
            payload = self.agent.announce(d)
        self.assertIsNone(payload)
        self.assertEqual(len(log.output), 1)
        self.assertEqual(len(log.records), 1)
        self.assertIn('response payload has no agentUuid', log.output[0])


    @patch.object(requests.Session, "get")
    def test_agent_connection_attempt(self, mock_requests_session_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests_session_get.return_value = mock_response

        self.create_agent_and_setup_tracer()
        host = self.agent.options.agent_host
        port = self.agent.options.agent_port
        msg = f"Instana host agent found on {host}:{port}"
        
        with self.assertLogs(logger, level='DEBUG') as log:
            result = self.agent.is_agent_listening(host, port)

        self.assertTrue(result)
        self.assertIn(msg, log.output[0])


    @patch.object(requests.Session, "get")
    def test_agent_connection_attempt_fails_with_404(self, mock_requests_session_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests_session_get.return_value = mock_response

        self.create_agent_and_setup_tracer()
        host = self.agent.options.agent_host
        port = self.agent.options.agent_port
        msg = "The attempt to connect to the Instana host agent on " \
              f"{host}:{port} has failed with an unexpected status code. " \
              f"Expected HTTP 200 but received: {mock_response.status_code}"

        with self.assertLogs(logger, level='DEBUG') as log:
            result = self.agent.is_agent_listening(host, port)

        self.assertFalse(result)
        self.assertIn(msg, log.output[0])
