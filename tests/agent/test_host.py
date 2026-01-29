# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import datetime
import json
import logging
import os
from typing import Any, Dict, Generator
from unittest.mock import Mock

import pytest
import requests
from mock import MagicMock, patch

from instana.agent.host import AnnounceData, HostAgent
from instana.collector.host import HostCollector
from instana.fsm import TheMachine
from instana.options import BaseOptions, StandardOptions
from instana.recorder import StanRecorder
from instana.singletons import get_agent
from instana.span.span import InstanaSpan
from instana.span.registered_span import RegisteredSpan
from instana.span_context import SpanContext
from instana.util.process_discovery import Discovery
from instana.util.runtime import is_windows


class TestHostAgent:
    @pytest.fixture(autouse=True)
    def _resource(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> Generator[None, None, None]:
        self.agent = get_agent()
        self.span_recorder = None
        self.tracer = None
        yield
        caplog.clear()
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

    def test_secrets(self) -> None:
        assert hasattr(self.agent.options, "secrets_matcher")
        assert self.agent.options.secrets_matcher == "contains-ignore-case"
        assert hasattr(self.agent.options, "secrets_list")
        assert self.agent.options.secrets_list == ["key", "pass", "secret"]

    def test_options_have_extra_http_headers(self) -> None:
        assert hasattr(self.agent, "options")
        assert hasattr(self.agent.options, "extra_http_headers")

    def test_has_options(self) -> None:
        assert hasattr(self.agent, "options")
        assert isinstance(self.agent.options, StandardOptions)

    def test_agent_default_log_level(self) -> None:
        assert self.agent.options.log_level == logging.WARNING

    def test_agent_instana_debug(self) -> None:
        os.environ["INSTANA_DEBUG"] = "asdf"
        self.agent.options = StandardOptions()
        assert self.agent.options.log_level == logging.DEBUG

    def test_agent_instana_service_name(self) -> None:
        os.environ["INSTANA_SERVICE_NAME"] = "greycake"
        self.agent.options = StandardOptions()
        assert self.agent.options.service_name == "greycake"

    @pytest.mark.original
    @patch.object(requests.Session, "put")
    def test_announce_is_successful(
        self,
        mock_requests_session_put: MagicMock,
    ) -> None:
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

    @pytest.mark.original
    @patch.object(requests.Session, "put")
    def test_announce_fails_with_non_200(
        self,
        mock_requests_session_put: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = ""
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        caplog.set_level(logging.DEBUG, logger="instana")
        caplog.clear()
        payload = self.agent.announce(d)
        assert payload is None
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "response status code" in caplog.messages[0]
        assert "is NOT 200" in caplog.messages[0]

    @pytest.mark.original
    @patch.object(requests.Session, "put")
    def test_announce_fails_with_non_json(
        self,
        mock_requests_session_put: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = ""
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        caplog.set_level(logging.DEBUG, logger="instana")
        caplog.clear()
        payload = self.agent.announce(d)
        assert payload is None
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "response is not JSON" in caplog.messages[0]

    @pytest.mark.original
    @patch.object(requests.Session, "put")
    def test_announce_fails_with_empty_list_json(
        self,
        mock_requests_session_put: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = "[]"
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        caplog.set_level(logging.DEBUG, logger="instana")
        caplog.clear()
        payload = self.agent.announce(d)
        assert payload is None
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "payload has no fields" in caplog.messages[0]

    @pytest.mark.original
    @patch.object(requests.Session, "put")
    def test_announce_fails_with_missing_pid(
        self,
        mock_requests_session_put: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
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
        caplog.clear()
        payload = self.agent.announce(d)
        assert payload is None
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "response payload has no pid" in caplog.messages[0]

    @pytest.mark.original
    @patch.object(requests.Session, "put")
    def test_announce_fails_with_missing_uuid(
        self,
        mock_requests_session_put: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        test_pid = 4242
        test_process_name = "test_process"
        test_process_args = ["-v", "-d"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = "{" f'  "pid": {test_pid} ' "}"
        mock_requests_session_put.return_value = mock_response

        d = Discovery(pid=test_pid, name=test_process_name, args=test_process_args)
        caplog.clear()
        payload = self.agent.announce(d)
        assert payload is None
        assert len(caplog.messages) == 1
        assert len(caplog.records) == 1
        assert "response payload has no agentUuid" in caplog.messages[0]

    @pytest.mark.original
    @patch.object(requests.Session, "get")
    def test_agent_connection_attempt(
        self,
        mock_requests_session_get: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
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
        self,
        mock_requests_session_get: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
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

        caplog.clear()
        result = self.agent.is_agent_listening(host, port)

        assert not result
        assert msg in caplog.messages[0]

    @pytest.mark.skipif(
        is_windows(),
        reason='Avoiding "psutil.NoSuchProcess: process PID not found (pid=12345)"',
    )
    def test_init(self) -> None:
        with patch(
            "instana.agent.base.BaseAgent.update_log_level"
        ) as mock_update, patch.object(os, "getpid", return_value=12345):
            agent = HostAgent()
            assert not agent.announce_data
            assert not agent.last_seen
            assert not agent.last_fork_check
            assert agent._boot_pid == 12345

            mock_update.assert_called_once()

            assert isinstance(agent.options, StandardOptions)
            assert isinstance(agent.collector, HostCollector)
            assert isinstance(agent.machine, TheMachine)

    def test_start(
        self,
    ) -> None:
        with patch("instana.collector.host.HostCollector.start") as mock_start:
            agent = HostAgent()
            agent.start()
            mock_start.assert_called_once()

    def test_handle_fork(
        self,
    ) -> None:
        with patch.object(HostAgent, "reset") as mock_reset:
            agent = HostAgent()
            agent.handle_fork()
            mock_reset.assert_called_once()

    def test_reset(
        self,
    ) -> None:
        with patch(
            "instana.collector.host.HostCollector.shutdown"
        ) as mock_shutdown, patch("instana.fsm.TheMachine.reset") as mock_reset:
            agent = HostAgent()
            agent.reset()

            assert not agent.last_seen
            assert not agent.announce_data

            mock_shutdown.assert_called_once_with(report_final=False)
            mock_reset.assert_called_once()

    def test_is_timed_out(
        self,
    ) -> None:
        agent = HostAgent()
        assert not agent.is_timed_out()

        agent.last_seen = datetime.datetime.now() - datetime.timedelta(minutes=5)
        agent.can_send = True
        assert agent.is_timed_out()

    def test_can_send_test_env(
        self,
    ) -> None:
        agent = HostAgent()
        with patch.dict("os.environ", {"INSTANA_TEST": "sample-data"}):
            if "INSTANA_TEST" in os.environ:
                assert agent.can_send()

    @pytest.mark.original
    def test_can_send(
        self,
    ) -> None:
        agent = HostAgent()
        agent._boot_pid = 12345
        with patch.object(os, "getpid", return_value=12344), patch(
            "instana.agent.host.HostAgent.handle_fork"
        ) as mock_handle, patch.dict("os.environ", {}, clear=True):
            agent.can_send()
            assert agent._boot_pid == 12344
            mock_handle.assert_called_once()

            with patch.object(agent.machine.fsm, "current", "wait4init"):
                assert agent.can_send() is True

    @pytest.mark.original
    def test_can_send_default(
        self,
    ) -> None:
        agent = HostAgent()
        with patch.dict("os.environ", {}, clear=True):
            assert not agent.can_send()

    def test_set_from(
        self,
    ) -> None:
        agent = HostAgent()
        sample_res_data = {
            "secrets": {"matcher": "value-1", "list": ["value-2"]},
            "extraHeaders": ["value-3"],
            "agentUuid": "value-4",
            "pid": 1234,
        }
        agent.options.extra_http_headers = None

        agent.set_from(sample_res_data)
        assert agent.options.secrets_matcher == "value-1"
        assert agent.options.secrets_list == ["value-2"]
        assert agent.options.extra_http_headers == ["value-3"]

        agent.options.extra_http_headers = ["value"]
        agent.set_from(sample_res_data)
        assert "value" in agent.options.extra_http_headers

        assert agent.announce_data.agentUuid == "value-4"
        assert agent.announce_data.pid == 1234

    def test_set_span_filters_from_agent_config(
        self,
    ) -> None:
        agent = HostAgent()
        sample_res_data = {
            "agentUuid": "value-4",
            "pid": 1234,
            "tracing": {
                "filter": {
                    "exclude": [
                        {
                            "name": "HTTP for filtering context root",
                            "attributes": [
                                {"key": "category", "values": ["protocols"]},
                                {
                                    "key": "http.context_root",
                                    "values": ["/health"],
                                    "match_type": "strict",
                                },
                            ],
                        },
                        {
                            "name": "HTTP",
                            "attributes": [
                                {"key": "category", "values": ["protocols"]},
                                {
                                    "key": "http.context_root",
                                    "values": ["/jetty"],
                                    "match_type": "strict",
                                },
                                {
                                    "key": "http.url",
                                    "match_type": "endswith",
                                    "values": ["/dawg"],
                                },
                            ],
                        },
                    ],
                    "include": [
                        {
                            "name": "HTTP",
                            "attributes": [
                                {"key": "category", "values": ["protocols"]},
                                {
                                    "key": "http.context_root",
                                    "values": ["/jetty"],
                                    "match_type": "strict",
                                },
                                {
                                    "key": "http.url",
                                    "match_type": "endswith",
                                    "values": ["/dawg"],
                                },
                            ],
                        }
                    ],
                },
            },
        }
        agent.options.extra_http_headers = None

        agent.set_from(sample_res_data)
        assert (
            agent.options.span_filters["exclude"][0]["name"]
            == sample_res_data["tracing"]["filter"]["exclude"][0]["name"]
        )
        assert agent.options.span_filters["exclude"][0]["attributes"] == [
            {
                "key": "category",
                "values": ["protocols"],
                "match_type": "strict",
            },
            {
                "key": "http.context_root",
                "values": ["/health"],
                "match_type": "strict",
            },
        ]
        assert (
            agent.options.span_filters["exclude"][1]["name"]
            == sample_res_data["tracing"]["filter"]["exclude"][1]["name"]
        )
        assert agent.options.span_filters["exclude"][1]["attributes"] == [
            {"key": "category", "values": ["protocols"], "match_type": "strict"},
            {
                "key": "http.context_root",
                "values": ["/jetty"],
                "match_type": "strict",
            },
            {
                "key": "http.url",
                "match_type": "endswith",
                "values": ["/dawg"],
            },
        ]
        assert (
            agent.options.span_filters["include"][0]["name"]
            == sample_res_data["tracing"]["filter"]["include"][0]["name"]
        )
        assert agent.options.span_filters["include"][0]["attributes"] == [
            {"key": "category", "values": ["protocols"], "match_type": "strict"},
            {
                "key": "http.context_root",
                "values": ["/jetty"],
                "match_type": "strict",
            },
            {
                "key": "http.url",
                "match_type": "endswith",
                "values": ["/dawg"],
            },
        ]

    @pytest.mark.original
    def test_get_from_structure(
        self,
    ) -> None:
        agent = HostAgent()
        agent.announce_data = AnnounceData(pid=1234, agentUuid="value")
        assert agent.get_from_structure() == {"e": 1234, "h": "value"}

    @pytest.mark.original
    def test_is_agent_listening(
        self,
        caplog,
    ) -> None:
        agent = HostAgent()
        mock_response = Mock()
        mock_response.status_code = 200
        with patch.object(requests.Session, "get", return_value=mock_response):
            assert agent.is_agent_listening("sample", 1234)

        mock_response.status_code = 404
        with patch.object(
            requests.Session, "get", return_value=mock_response, clear=True
        ):
            assert not agent.is_agent_listening("sample", 1234)

        host = "localhost"
        port = 123
        with patch.object(requests.Session, "get", side_effect=Exception()):
            caplog.set_level(logging.DEBUG, logger="instana")
            agent.is_agent_listening(host, port)
            assert f"Instana Host Agent not found on {host}:{port}" in caplog.messages

    @pytest.mark.original
    def test_announce(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        agent = HostAgent()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(
            {"get": "value", "pid": "value", "agentUuid": "value"}
        )
        response = json.loads(mock_response.content)
        with patch.object(requests.Session, "put", return_value=mock_response):
            assert agent.announce("sample-data") == response

        mock_response.content = mock_response.content.encode("UTF-8")
        with patch.object(requests.Session, "put", return_value=mock_response):
            assert agent.announce("sample-data") == response

        mock_response.content = json.dumps(
            {"get": "value", "pid": "value", "agentUuid": "value"}
        )

        with patch.object(requests.Session, "put", side_effect=Exception()):
            caplog.set_level(logging.DEBUG, logger="instana")
            assert not agent.announce("sample-data")
            assert (
                f"announce: connection error ({type(Exception())})" in caplog.messages
            )

        mock_response.content = json.dumps("key")
        with patch.object(
            requests.Session, "put", return_value=mock_response, clear=True
        ):
            caplog.set_level(logging.DEBUG, logger="instana")
            assert not agent.announce("sample-data")
            assert "announce: response payload has no fields: (key)" in caplog.messages

        mock_response.content = json.dumps({"key": "value"})
        with patch.object(
            requests.Session, "put", return_value=mock_response, clear=True
        ):
            caplog.set_level(logging.DEBUG, logger="instana")
            assert not agent.announce("sample-data")
            assert (
                "announce: response payload has no pid: ({'key': 'value'})"
                in caplog.messages
            )

        mock_response.content = json.dumps({"pid": "value"})
        with patch.object(
            requests.Session, "put", return_value=mock_response, clear=True
        ):
            caplog.set_level(logging.DEBUG, logger="instana")
            assert not agent.announce("sample-data")
            assert (
                "announce: response payload has no agentUuid: ({'pid': 'value'})"
                in caplog.messages
            )

        mock_response.status_code = 404
        with patch.object(
            requests.Session, "put", return_value=mock_response, clear=True
        ):
            assert not agent.announce("sample-data")
            assert "announce: response status code (404) is NOT 200" in caplog.messages

    def test_log_message_to_host_agent(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        agent = HostAgent()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.return_value = "sample"
        mock_datetime = datetime.datetime(2022, 1, 1, 12, 0, 0)
        with patch.object(requests.Session, "post", return_value=mock_response), patch(
            "instana.agent.host.datetime"
        ) as mock_date:
            mock_date.now.return_value = mock_datetime
            mock_date.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            agent.log_message_to_host_agent("sample")
            assert agent.last_seen == mock_datetime

            with patch.object(requests.Session, "post", side_effect=Exception()):
                caplog.set_level(logging.DEBUG, logger="instana")
                agent.log_message_to_host_agent("sample")
                assert (
                    f"agent logging: connection error ({type(Exception())})"
                    in caplog.messages
                )

    def test_is_agent_ready(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        agent = HostAgent()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.return_value = {"key": "value"}
        agent.AGENT_DATA_PATH = "sample_path"
        agent.announce_data = AnnounceData(pid=1234, agentUuid="sample")
        with patch.object(requests.Session, "head", return_value=mock_response), patch(
            "instana.agent.host.HostAgent._HostAgent__data_url",
            return_value="localhost",
        ):
            assert agent.is_agent_ready()
            with patch.object(requests.Session, "head", side_effect=Exception()):
                caplog.set_level(logging.DEBUG, logger="instana")
                agent.is_agent_ready()
                assert (
                    f"is_agent_ready: connection error ({type(Exception())})"
                    in caplog.messages
                )

    def test_report_data_payload(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        agent = HostAgent()
        span_name = "test-span"
        span_1 = InstanaSpan(span_name, span_context, span_processor)
        span_2 = InstanaSpan(span_name, span_context, span_processor)
        payload = {
            "spans": [span_1, span_2],
            "profiles": ["profile-1", "profile-2"],
            "metrics": {
                "plugins": [
                    {"data": "sample data"},
                ]
            },
        }
        sample_response = {"key": "value"}
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_response
        with patch.object(requests.Session, "post", return_value=mock_response), patch(
            "instana.agent.host.HostAgent._HostAgent__traces_url",
            return_value="localhost",
        ), patch(
            "instana.agent.host.HostAgent._HostAgent__profiles_url",
            return_value="localhost",
        ), patch(
            "instana.agent.host.HostAgent._HostAgent__data_url",
            return_value="localhost",
        ):
            test_response = agent.report_data_payload(payload)
            assert isinstance(agent.last_seen, datetime.datetime)
            assert test_response.content == sample_response

    def test_report_metrics(self) -> None:
        agent = HostAgent()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.return_value = "Success"

        payload = {
            "metrics": {
                "plugins": [
                    {"data": "sample data"},
                ]
            },
        }

        with patch.object(requests.Session, "post", return_value=mock_response), patch(
            "instana.agent.host.HostAgent._HostAgent__traces_url",
            return_value="localhost",
        ), patch(
            "instana.agent.host.HostAgent._HostAgent__profiles_url",
            return_value="localhost",
        ), patch(
            "instana.agent.host.HostAgent._HostAgent__data_url",
            return_value="localhost",
        ):
            test_response = agent.report_metrics(payload)
            assert test_response.return_value == "Success"

    def test_report_profiles(self) -> None:
        agent = HostAgent()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.return_value = "Success"

        payload = {
            "profiles": ["profile-1", "profile-2"],
        }

        with patch.object(requests.Session, "post", return_value=mock_response), patch(
            "instana.agent.host.HostAgent._HostAgent__traces_url",
            return_value="localhost",
        ), patch(
            "instana.agent.host.HostAgent._HostAgent__profiles_url",
            return_value="localhost",
        ), patch(
            "instana.agent.host.HostAgent._HostAgent__data_url",
            return_value="localhost",
        ):
            test_response = agent.report_profiles(payload)
            assert test_response.return_value == "Success"

    def test_report_spans(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        agent = HostAgent()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.return_value = "Success"

        span_name = "test_span"
        span_1 = InstanaSpan(span_name, span_context, span_processor)
        span_2 = InstanaSpan(span_name, span_context, span_processor)

        payload = {
            "spans": [span_1, span_2],
        }

        with patch.object(requests.Session, "post", return_value=mock_response), patch(
            "instana.agent.host.HostAgent._HostAgent__traces_url",
            return_value="localhost",
        ), patch(
            "instana.agent.host.HostAgent._HostAgent__profiles_url",
            return_value="localhost",
        ), patch(
            "instana.agent.host.HostAgent._HostAgent__data_url",
            return_value="localhost",
        ):
            test_response = agent.report_spans(payload)
            assert test_response.return_value == "Success"

    def test_diagnostics(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING, logger="instana")

        agent = HostAgent()
        agent.diagnostics()
        assert (
            "====> Instana Python Language Agent Diagnostics <====" in caplog.messages
        )
        assert "----> Agent <----" in caplog.messages
        assert f"is_agent_ready: {agent.is_agent_ready()}" in caplog.messages
        assert f"is_timed_out: {agent.is_timed_out()}" in caplog.messages
        assert "last_seen: None" in caplog.messages

        sample_date = datetime.datetime(2022, 7, 25, 14, 30, 0)
        agent.last_seen = sample_date
        agent.diagnostics()
        assert "last_seen: 2022-07-25 14:30:00" in caplog.messages
        assert "announce_data: None" in caplog.messages

        agent.announce_data = AnnounceData(pid=1234, agentUuid="value")
        agent.diagnostics()
        assert f"announce_data: {agent.announce_data.__dict__}" in caplog.messages
        assert f"Options: {agent.options.__dict__}" in caplog.messages
        assert "----> StateMachine <----" in caplog.messages
        assert f"State: {agent.machine.fsm.current}" in caplog.messages
        assert "----> Collector <----" in caplog.messages
        assert f"Collector: {agent.collector}" in caplog.messages
        assert f"ready_to_start: {agent.collector.ready_to_start}" in caplog.messages
        assert "reporting_thread: None" in caplog.messages
        assert f"report_interval: {agent.collector.report_interval}" in caplog.messages
        assert "should_send_snapshot_data: True" in caplog.messages

    @patch.dict(
        os.environ,
        {"INSTANA_CONFIG_PATH": "tests/util/test_span_filter.yaml"},
    )
    def test_is_service_or_endpoint_ignored(self) -> None:
        self.agent.options = BaseOptions()
        self.agent.options.ignore_endpoints.append("service1.*")
        self.agent.options.ignore_endpoints.append("service2.method1")

        # ignore all endpoints of service1
        assert self.agent._HostAgent__is_endpoint_ignored("service1")
        assert self.agent._HostAgent__is_endpoint_ignored("service1", "method1")
        assert self.agent._HostAgent__is_endpoint_ignored("service1", "method2")

        # case-insensitive
        assert self.agent._HostAgent__is_endpoint_ignored("SERVICE1")
        assert self.agent._HostAgent__is_endpoint_ignored("service1", "METHOD1")

        # ignore only endpoint1 of service2
        assert self.agent._HostAgent__is_endpoint_ignored("service2", "method1")
        assert not self.agent._HostAgent__is_endpoint_ignored("service2", "method2")

        # don't ignore other services
        assert not self.agent._HostAgent__is_endpoint_ignored("service3")
        assert not self.agent._HostAgent__is_endpoint_ignored("service3")

    def test_span_filtering_with_exclude_rule(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test span filtering with exclude rules."""
        # Setup span_filters configuration
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Kafka filter",
                    "attributes": [
                        {"key": "type", "values": ["kafka"], "match_type": "strict"},
                        {
                            "key": "kafka.service",
                            "values": ["topic1", "topic2"],
                            "match_type": "contains",
                        },
                    ],
                }
            ]
        }

        # Create span that should be filtered
        instana_span1 = InstanaSpan("kafka-consumer", span_context, span_processor)
        instana_span1.set_attribute("kafka.service", "topic1")
        instana_span1.set_attribute("kafka.access", "consume")
        filtered_span = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )

        assert self.agent._HostAgent__is_span_filtered(filtered_span) is True

        # Create span that should NOT be filtered (different topic)
        instana_span2 = InstanaSpan("kafka-consumer", span_context, span_processor)
        instana_span2.set_attribute("kafka.service", "topic3")
        instana_span2.set_attribute("kafka.access", "consume")
        kept_span = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )

        assert self.agent._HostAgent__is_span_filtered(kept_span) is False

    def test_span_filtering_with_include_rule(self) -> None:
        """Test span filtering with include rules (higher precedence)."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude all HTTP",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["protocols"],
                            "match_type": "strict",
                        },
                    ],
                }
            ],
            "include": [
                {
                    "name": "Include specific URL",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["protocols"],
                            "match_type": "strict",
                        },
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "contains",
                        },
                    ],
                }
            ],
        }

        # Create HTTP span with /health URL - should be INCLUDED (not filtered)
        class MockHttpSpan:
            def __init__(self):
                self.n = "http"
                self.k = 0  # SpanKind.SERVER
                self.data = {"http": {"url": "/api/health", "method": "GET"}}

        health_span = MockHttpSpan()
        assert self.agent._HostAgent__is_span_filtered(health_span) is False

        # Create HTTP span without /health - should be EXCLUDED (filtered)
        class MockHttpSpan2:
            def __init__(self):
                self.n = "http"
                self.k = 0
                self.data = {"http": {"url": "/api/users", "method": "GET"}}

        other_span = MockHttpSpan2()
        assert self.agent._HostAgent__is_span_filtered(other_span) is True

    def test_span_filtering_match_types(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test different match types: strict, startswith, endswith, contains."""
        # Test startswith
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Filter URLs starting with /api",
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/api"],
                            "match_type": "startswith",
                        },
                    ],
                }
            ]
        }

        instana_span1 = InstanaSpan("django", span_context, span_processor)
        instana_span1.set_attribute("http.url", "/api/users")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.url", "/health")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is False

        # Test endswith
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Filter URLs ending with .json",
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": [".json"],
                            "match_type": "endswith",
                        },
                    ],
                }
            ]
        }

        instana_span3 = InstanaSpan("django", span_context, span_processor)
        instana_span3.set_attribute("http.url", "/data.json")
        span3 = RegisteredSpan(
            instana_span3, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span3) is True

        instana_span4 = InstanaSpan("django", span_context, span_processor)
        instana_span4.set_attribute("http.url", "/data.xml")
        span4 = RegisteredSpan(
            instana_span4, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span4) is False

    def test_span_filtering_defensive_behavior(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that filtering fails gracefully and keeps spans on error."""
        # Empty span_filters should not filter
        self.agent.options.span_filters = {}

        instana_span = InstanaSpan("django", span_context, span_processor)
        instana_span.set_attribute("http.url", "/test")
        span = RegisteredSpan(instana_span, {"e": "test", "h": "test"}, "test-service")
        assert self.agent._HostAgent__is_span_filtered(span) is False

    def test_is_span_filtered_no_filters_configured(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test __is_span_filtered returns False when no filters are configured."""
        self.agent.options.span_filters = None

        instana_span = InstanaSpan("django", span_context, span_processor)
        instana_span.set_attribute("http.url", "/test")
        span = RegisteredSpan(instana_span, {"e": "test", "h": "test"}, "test-service")

        assert self.agent._HostAgent__is_span_filtered(span) is False

    def test_is_span_filtered_exclude_by_category(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test __is_span_filtered with category-based exclusion."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude databases",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["databases"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        # Database span should be filtered
        instana_span1 = InstanaSpan("redis", span_context, span_processor)
        instana_span1.set_attribute("redis.command", "GET")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # HTTP span should NOT be filtered
        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.url", "/test")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is False

    def test_is_span_filtered_exclude_by_kind(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test __is_span_filtered with kind-based exclusion."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude exit spans",
                    "attributes": [
                        {"key": "kind", "values": ["exit"], "match_type": "strict"},
                    ],
                }
            ]
        }

        # Exit span should be filtered
        instana_span1 = InstanaSpan("redis", span_context, span_processor)
        instana_span1.set_attribute("redis.command", "GET")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

    def test_is_span_filtered_multiple_exclude_rules(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test __is_span_filtered with multiple exclude rules (OR logic)."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude Redis GET",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["GET"],
                            "match_type": "strict",
                        },
                    ],
                },
                {
                    "name": "Exclude HTTP /health",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["protocols"],
                            "match_type": "strict",
                        },
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "contains",
                        },
                    ],
                },
            ]
        }

        # Redis GET should be filtered (first rule)
        instana_span1 = InstanaSpan("redis", span_context, span_processor)
        instana_span1.set_attribute("redis.command", "GET")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # HTTP /health should be filtered (second rule)
        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.url", "/api/health")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is True

        # Redis SET should NOT be filtered
        instana_span3 = InstanaSpan("redis", span_context, span_processor)
        instana_span3.set_attribute("redis.command", "SET")
        span3 = RegisteredSpan(
            instana_span3, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span3) is False

    def test_is_span_filtered_include_overrides_exclude(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that include rules have higher precedence than exclude rules."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude all Redis",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                    ],
                }
            ],
            "include": [
                {
                    "name": "Include Redis GET",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["GET"],
                            "match_type": "strict",
                        },
                    ],
                }
            ],
        }

        # Redis GET should NOT be filtered (include rule)
        instana_span1 = InstanaSpan("redis", span_context, span_processor)
        instana_span1.set_attribute("redis.command", "GET")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is False

        # Redis SET should be filtered (exclude rule, no include match)
        instana_span2 = InstanaSpan("redis", span_context, span_processor)
        instana_span2.set_attribute("redis.command", "SET")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is True

    def test_is_span_filtered_multiple_values_or_logic(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that multiple values in an attribute use OR logic."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude specific commands",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["GET", "SET", "DEL"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        # GET should be filtered
        instana_span1 = InstanaSpan("redis", span_context, span_processor)
        instana_span1.set_attribute("redis.command", "GET")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # SET should be filtered
        instana_span2 = InstanaSpan("redis", span_context, span_processor)
        instana_span2.set_attribute("redis.command", "SET")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is True

        # DEL should be filtered
        instana_span3 = InstanaSpan("redis", span_context, span_processor)
        instana_span3.set_attribute("redis.command", "DEL")
        span3 = RegisteredSpan(
            instana_span3, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span3) is True

        # INCR should NOT be filtered
        instana_span4 = InstanaSpan("redis", span_context, span_processor)
        instana_span4.set_attribute("redis.command", "INCR")
        span4 = RegisteredSpan(
            instana_span4, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span4) is False

    def test_is_span_filtered_and_logic_within_rule(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that attributes within a rule use AND logic (all must match)."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude specific Redis GET",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["GET"],
                            "match_type": "strict",
                        },
                        {
                            "key": "category",
                            "values": ["databases"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        # All conditions match - should be filtered
        instana_span1 = InstanaSpan("redis", span_context, span_processor)
        instana_span1.set_attribute("redis.command", "GET")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # Only type and category match, command is SET - should NOT be filtered
        instana_span2 = InstanaSpan("redis", span_context, span_processor)
        instana_span2.set_attribute("redis.command", "SET")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is False

    def test_is_span_filtered_contains_match_type(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test __is_span_filtered with contains match type."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Filter URLs containing 'admin'",
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["admin"],
                            "match_type": "contains",
                        },
                    ],
                }
            ]
        }

        # URL containing 'admin' should be filtered
        instana_span1 = InstanaSpan("django", span_context, span_processor)
        instana_span1.set_attribute("http.url", "/api/admin/users")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # URL not containing 'admin' should NOT be filtered
        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.url", "/api/users")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is False

    def test_filter_spans_integration(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test filter_spans method with span_filters configuration."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Test Filter",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["protocols"],
                            "match_type": "strict",
                        },
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "contains",
                        },
                    ],
                }
            ]
        }

        # Create spans
        instana_span1 = InstanaSpan("django", span_context, span_processor)
        instana_span1.set_attribute("http.url", "/api/health")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )

        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.url", "/api/users")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )

        # Test filter_spans method
        spans = [span1, span2]
        filtered = self.agent.filter_spans(spans)

        # Only span2 should remain (span1 filtered out)
        assert len(filtered) == 1
        assert filtered[0] == span2

    def test_http_filter_context_root(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test filtering out a specific context root (/health)."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "HTTP for filtering context root",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["protocols"],
                            "match_type": "strict",
                        },
                        {
                            "key": "http.path",
                            "values": ["/health"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        # Create span with /health path - should be filtered
        instana_span1 = InstanaSpan("django", span_context, span_processor)
        instana_span1.set_attribute("http.path", "/health")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # Create span with different path - should NOT be filtered
        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.path", "/api/users")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is False

    def test_http_filter_url_and_method(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test filtering with URL contains and specific method."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "HTTP",
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/hello/dawg"],
                            "match_type": "contains",
                        },
                        {
                            "key": "http.method",
                            "values": ["GET"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        # Should be filtered (contains /hello/dawg AND method is GET)
        instana_span1 = InstanaSpan("django", span_context, span_processor)
        instana_span1.set_attribute("http.url", "/jetty/controller/hello/dawg")
        instana_span1.set_attribute("http.method", "GET")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # Should NOT be filtered (contains /hello/dawg but method is POST)
        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.url", "/jetty/controller/hello/dawg")
        instana_span2.set_attribute("http.method", "POST")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is False

    def test_http_filter_multiple_url_conditions(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test filtering with URL starting with /jetty AND ending with /dawg."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "HTTP",
                    "attributes": [
                        {
                            "key": "http.url",
                            "values": ["/jetty"],
                            "match_type": "startswith",
                        },
                        {
                            "key": "http.url",
                            "values": ["/dawg"],
                            "match_type": "endswith",
                        },
                    ],
                }
            ]
        }

        # Should be filtered (starts with /jetty AND ends with /dawg)
        instana_span1 = InstanaSpan("django", span_context, span_processor)
        instana_span1.set_attribute("http.url", "/jetty/controller/hello/dawg")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # Should NOT be filtered (starts with /jetty but doesn't end with /dawg)
        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.url", "/jetty/controller/hello/cat")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is False

    def test_kafka_filter_by_topics(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test filtering Kafka calls based on specific topics."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Kafka",
                    "attributes": [
                        {"key": "type", "values": ["kafka"], "match_type": "strict"},
                        {
                            "key": "kafka.service",
                            "values": ["topic1", "topic2"],
                            "match_type": "contains",
                        },
                    ],
                }
            ]
        }

        # Should be filtered (topic1)
        instana_span1 = InstanaSpan("kafka-consumer", span_context, span_processor)
        instana_span1.set_attribute("kafka.service", "topic1")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is True

        # Should be filtered (topic2)
        instana_span2 = InstanaSpan("kafka-consumer", span_context, span_processor)
        instana_span2.set_attribute("kafka.service", "topic2")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is True

        # Should NOT be filtered (topic3)
        instana_span3 = InstanaSpan("kafka-consumer", span_context, span_processor)
        instana_span3.set_attribute("kafka.service", "topic3")
        span3 = RegisteredSpan(
            instana_span3, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span3) is False

    def test_kafka_filter_by_kind(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test filtering Kafka calls using kind (entry/exit)."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Kafka",
                    "attributes": [
                        {"key": "type", "values": ["kafka"], "match_type": "strict"},
                        {
                            "key": "kind",
                            "values": ["entry", "exit"],
                            "match_type": "strict",
                        },
                        {
                            "key": "kafka.service",
                            "values": ["topic1"],
                            "match_type": "contains",
                        },
                    ],
                }
            ]
        }

        # Should be filtered (entry span with topic1)
        instana_span1 = InstanaSpan("kafka-consumer", span_context, span_processor)
        instana_span1.set_attribute("kafka.service", "topic1")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        # kafka-consumer creates entry span (SpanKind.SERVER)
        assert self.agent._HostAgent__is_span_filtered(span1) is True

    def test_kafka_separate_producer_consumer_filters(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test separate filters for Kafka producer (topic1) and consumer (topic2)."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Kafka Producer",
                    "attributes": [
                        {"key": "type", "values": ["kafka"], "match_type": "strict"},
                        {"key": "kind", "values": ["exit"], "match_type": "strict"},
                        {
                            "key": "kafka.service",
                            "values": ["topic1"],
                            "match_type": "contains",
                        },
                    ],
                },
                {
                    "name": "Kafka Consumer",
                    "attributes": [
                        {"key": "type", "values": ["kafka"], "match_type": "strict"},
                        {"key": "kind", "values": ["entry"], "match_type": "strict"},
                        {
                            "key": "kafka.service",
                            "values": ["topic2"],
                            "match_type": "contains",
                        },
                    ],
                },
            ]
        }

        # Consumer with topic1 - should NOT be filtered (only producer topic1 is filtered)
        instana_span1 = InstanaSpan("kafka-consumer", span_context, span_processor)
        instana_span1.set_attribute("kafka.service", "topic1")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is False

        # Consumer with topic2 - should be filtered
        instana_span2 = InstanaSpan("kafka-consumer", span_context, span_processor)
        instana_span2.set_attribute("kafka.service", "topic2")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is True

    def test_include_exclude_precedence(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        """Test that include rules have higher precedence than exclude rules."""
        self.agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude all HTTP",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["protocols"],
                            "match_type": "strict",
                        },
                    ],
                }
            ],
            "include": [
                {
                    "name": "Include /health",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["protocols"],
                            "match_type": "strict",
                        },
                        {
                            "key": "http.url",
                            "values": ["/health"],
                            "match_type": "contains",
                        },
                    ],
                }
            ],
        }

        # Should be INCLUDED (include rule matches)
        instana_span1 = InstanaSpan("django", span_context, span_processor)
        instana_span1.set_attribute("http.url", "/api/health")
        span1 = RegisteredSpan(
            instana_span1, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span1) is False

        # Should be EXCLUDED (only exclude rule matches)
        instana_span2 = InstanaSpan("django", span_context, span_processor)
        instana_span2.set_attribute("http.url", "/api/users")
        span2 = RegisteredSpan(
            instana_span2, {"e": "test", "h": "test"}, "test-service"
        )
        assert self.agent._HostAgent__is_span_filtered(span2) is True

    @pytest.mark.parametrize(
        "input_data",
        [
            {
                "agentUuid": "test-uuid",
            },
            {
                "pid": 1234,
            },
            {
                "extraHeaders": ["value-3"],
            },
        ],
        ids=["missing_pid", "missing_agent_uuid", "missing_both_required_keys"],
    )
    def test_set_from_missing_required_keys(
        self, input_data: Dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test set_from when required keys are missing in res_data."""
        agent = HostAgent()
        caplog.set_level(logging.DEBUG, logger="instana")

        res_data = {
            "secrets": {"matcher": "value-1", "list": ["value-2"]},
        }
        res_data.update(input_data)

        agent.set_from(res_data)

        assert agent.announce_data is None
        assert "Missing required keys in announce response" in caplog.messages[-1]
        assert str(res_data) in caplog.messages[-1]
