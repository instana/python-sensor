# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import logging
import os
from typing import Generator

import pytest
import requests
from mock import MagicMock, patch

from instana.fsm import Discovery
from instana.options import StandardOptions
from instana.singletons import get_agent


class TestHost:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.agent = get_agent()
        self.span_processor = None
        self.agent.options = StandardOptions()
        pass
        variable_names = (
            "AWS_EXECUTION_ENV",
            "INSTANA_EXTRA_HTTP_HEADERS",
            "INSTANA_ENDPOINT_URL",
            "INSTANA_ENDPOINT_PROXY",
            "INSTANA_AGENT_KEY",
            "INSTANA_LOG_LEVEL",
            "INSTANA_SERVICE_NAME",
            "INSTANA_SECRETS",
            "INSTANA_TAGS",
        )

        for variable_name in variable_names:
            if variable_name in os.environ:
                os.environ.pop(variable_name)

    def test_secrets(self):
        assert hasattr(self.agent.options, "secrets_matcher")
        assert self.agent.options.secrets_matcher == "contains-ignore-case"
        assert hasattr(self.agent.options, "secrets_list")
        assert self.agent.options.secrets_list == ["key", "pass", "secret"]

    def test_options_have_extra_http_headers(self):
        assert hasattr(self.agent, "options")
        assert hasattr(self.agent.options, "extra_http_headers")

    def test_has_options(self):
        assert hasattr(self.agent, "options")
        assert isinstance(self.agent.options, StandardOptions)

    def test_agent_default_log_level(self):
        assert self.agent.options.log_level == logging.DEBUG

    def test_agent_instana_debug(self):
        os.environ["INSTANA_DEBUG"] = "asdf"
        self.agent.options = StandardOptions()
        assert self.agent.options.log_level == logging.DEBUG

    def test_agent_instana_service_name(self):
        os.environ["INSTANA_SERVICE_NAME"] = "greycake"
        self.agent.options = StandardOptions()
        assert self.agent.options.service_name == "greycake"

    @patch.object(requests.Session, "put")
    def test_announce_is_successful(self, mock_requests_session_put):
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]
        test_agent_uuid = "83bf1e09-ab16-4203-abf5-34ee0977023a"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = (
            "{" f'  "pid": {test_pid}, ' f'  "agentUuid": "{test_agent_uuid}"' "}"
        )

        # This mocks the call to self.agent.client.put
        mock_requests_session_put.return_value = mock_response
        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        payload = self.agent.announce(d)

        assert "pid" in payload
        assert test_pid == payload["pid"]

        assert "agentUuid" in payload
        assert test_agent_uuid == payload["agentUuid"]

    @patch.object(requests.Session, "put")
    def test_announce_fails_with_non_200(self, mock_requests_session_put, caplog):
        caplog.set_level(logging.DEBUG, logger="instana")
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]
        test_agent_uuid = "83bf1e09-ab16-4203-abf5-34ee0977023a"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = ""
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)

        payload = self.agent.announce(d)
        assert not payload
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "response status code" in caplog.messages[0]
        assert "is NOT 200" in caplog.messages[0]

    @patch.object(requests.Session, "put")
    def test_announce_fails_with_non_json(self, mock_requests_session_put, caplog):
        caplog.set_level(logging.DEBUG, logger="instana")
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]
        test_agent_uuid = "83bf1e09-ab16-4203-abf5-34ee0977023a"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = ""
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        payload = self.agent.announce(d)
        assert not payload
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "response is not JSON" in caplog.messages[0]

    @patch.object(requests.Session, "put")
    def test_announce_fails_with_empty_list_json(
        self, mock_requests_session_put, caplog
    ):
        caplog.set_level(logging.DEBUG, logger="instana")
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]
        test_agent_uuid = "83bf1e09-ab16-4203-abf5-34ee0977023a"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = "[]"
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        payload = self.agent.announce(d)
        assert not payload
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "payload has no fields" in caplog.messages[0]

    @patch.object(requests.Session, "put")
    def test_announce_fails_with_missing_pid(self, mock_requests_session_put, caplog):
        caplog.set_level(logging.DEBUG, logger="instana")
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]
        test_agent_uuid = "83bf1e09-ab16-4203-abf5-34ee0977023a"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = "{" f'  "agentUuid": "{test_agent_uuid}"' "}"
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        payload = self.agent.announce(d)
        assert not payload
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "response payload has no pid" in caplog.messages[0]

    @patch.object(requests.Session, "put")
    def test_announce_fails_with_missing_uuid(self, mock_requests_session_put, caplog):
        caplog.set_level(logging.DEBUG, logger="instana")
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]
        test_agent_uuid = "83bf1e09-ab16-4203-abf5-34ee0977023a"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = "{" f'  "pid": {test_pid} ' "}"
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        payload = self.agent.announce(d)
        assert not payload
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "response payload has no agentUuid" in caplog.messages[0]

    @pytest.mark.original
    @patch.object(requests.Session, "get")
    def test_agent_connection_attempt(self, mock_requests_session_get, caplog):
        caplog.set_level(logging.DEBUG, logger="instana")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests_session_get.return_value = mock_response

        host = self.agent.options.agent_host
        port = self.agent.options.agent_port
        msg = f"Instana host agent found on {host}:{port}"

        result = self.agent.is_agent_listening(host, port)

        assert result
        assert msg in caplog.messages[0]

    @pytest.mark.original
    @patch.object(requests.Session, "get")
    def test_agent_connection_attempt_fails_with_404(
        self, mock_requests_session_get, caplog
    ):
        caplog.set_level(logging.DEBUG, logger="instana")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests_session_get.return_value = mock_response

        host = self.agent.options.agent_host
        port = self.agent.options.agent_port
        msg = (
            "The attempt to connect to the Instana host agent on "
            f"{host}:{port} has failed with an unexpected status code. "
            f"Expected HTTP 200 but received: {mock_response.status_code}"
        )

        result = self.agent.is_agent_listening(host, port)

        assert not result
        assert msg in caplog.messages[0]
