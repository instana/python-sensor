# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import datetime
import json
import logging
import os
from typing import Generator
from unittest.mock import Mock

import pytest
import requests
from mock import MagicMock, patch

from instana.agent.host import AnnounceData, HostAgent
from instana.collector.host import HostCollector
from instana.fsm import Discovery, TheMachine
from instana.options import StandardOptions
from instana.recorder import StanRecorder
from instana.singletons import get_agent
from instana.span.span import InstanaSpan
from instana.span_context import SpanContext


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

    def test_is_service_or_endpoint_ignored(self) -> None:
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
