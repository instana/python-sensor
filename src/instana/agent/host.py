# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
The in-process Instana agent (for host based processes) that manages
monitoring state and reporting that data.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import requests
import urllib3
from requests import Response

from instana.agent.base import BaseAgent
from instana.collector.host import HostCollector
from instana.fsm import Discovery, TheMachine
from instana.log import logger
from instana.options import StandardOptions
from instana.util import to_json
from instana.util.runtime import get_py_source, log_runtime_env_info
from instana.util.span_utils import get_operation_specifiers
from instana.version import VERSION


class AnnounceData(object):
    """The Announce Payload"""

    pid = 0
    agentUuid = ""

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class HostAgent(BaseAgent):
    """
    The Agent class is the central controlling entity for the Instana Python language sensor.  The key
    parts it handles are the announce state and the collection and reporting of metrics and spans to the
    Instana Host agent.
    """

    AGENT_DISCOVERY_PATH = "com.instana.plugin.python.discovery"
    AGENT_DATA_PATH = "com.instana.plugin.python.%d"

    def __init__(self) -> None:
        super(HostAgent, self).__init__()

        self.announce_data = None
        self.machine = None
        self.last_seen = None
        self.last_fork_check = None
        self._boot_pid = os.getpid()
        self.options = StandardOptions()

        # Update log level from what Options detected
        self.update_log_level()

        logger.info(
            f"Stan is on the scene.  Starting Instana instrumentation version: {VERSION}"
        )
        log_runtime_env_info()

        self.collector = HostCollector(self)
        self.machine = TheMachine(self)

    def start(self) -> None:
        """
        Starts the agent and required threads

        This method is called after a successful announce.  See fsm.py
        """
        logger.debug("Starting Host Collector")
        self.collector.start()

    def handle_fork(self) -> None:
        """
        Forks happen.  Here we handle them.
        """
        # Reset the Agent
        self.reset()

    def reset(self) -> None:
        """
        This will reset the agent to a fresh unannounced state.
        :return: None
        """
        self.last_seen = None
        self.announce_data = None
        self.collector.shutdown(report_final=False)

        # Will schedule a restart of the announce cycle in the future
        self.machine.reset()

    def is_timed_out(self) -> bool:
        """
        If we haven't heard from the Instana host agent in 60 seconds, this
        method will return True.
        @return: Boolean
        """
        if self.last_seen and self.can_send:
            diff = datetime.now() - self.last_seen
            if diff.seconds > 60:
                return True
        return False

    def can_send(self) -> bool:
        """
        Are we in a state where we can send data?
        @return: Boolean
        """
        # Watch for pid change (fork)
        self.last_fork_check = datetime.now()
        current_pid = os.getpid()
        if self._boot_pid != current_pid:
            self._boot_pid = current_pid
            logger.debug("Fork detected; Handling like a pro...")
            self.handle_fork()

        if self.machine.fsm.current in ["wait4init", "good2go"]:
            return True

        return False

    def set_from(
        self,
        res_data: Dict[str, Any],
    ) -> None:
        """
        Sets the source identifiers given to use by the Instana Host agent.
        @param res_data: source identifiers provided as announce response
        @return: None
        """
        self.options.set_from(res_data)
        self.announce_data = AnnounceData(
            pid=res_data["pid"],
            agentUuid=res_data["agentUuid"],
        )

    def get_from_structure(self) -> Dict[str, str]:
        """
        Retrieves the From data that is reported alongside monitoring data.
        @return: dict()
        """
        return {"e": self.announce_data.pid, "h": self.announce_data.agentUuid}

    def is_agent_listening(
        self,
        host: str,
        port: Union[str, int],
    ) -> bool:
        """
        Check if the Instana Agent is listening on <host> and <port>.
        @return: Boolean
        """
        result = False
        try:
            url = f"http://{host}:{port}/"
            response = self.client.get(url, timeout=5)

            if 200 <= response.status_code < 300:
                logger.debug(f"Instana host agent found on {host}:{port}")
                result = True
            else:
                logger.debug(
                    "The attempt to connect to the Instana host "
                    f"agent on {host}:{port} has failed with an unexpected "
                    f"status code. Expected HTTP 200 but received: {response.status_code}"
                )
        except Exception:
            logger.debug(f"Instana Host Agent not found on {host}:{port}")
        return result

    def announce(
        self,
        discovery: Discovery,
    ) -> Optional[Dict[str, Any]]:
        """
        With the passed in Discovery class, attempt to announce to the host agent.
        """
        try:
            url = self.__discovery_url()
            response = self.client.put(
                url,
                data=to_json(discovery),
                headers={"Content-Type": "application/json"},
                timeout=0.8,
            )
        except Exception as exc:
            logger.debug(f"announce: connection error ({type(exc)})")
            return None

        if 200 <= response.status_code <= 204:
            self.last_seen = datetime.now()

        if response.status_code != 200:
            logger.debug(
                f"announce: response status code ({response.status_code}) is NOT 200"
            )
            return None

        if isinstance(response.content, bytes):
            raw_json = response.content.decode("UTF-8")
        else:
            raw_json = response.content

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.debug(f"announce: response is not JSON: ({raw_json})")
            return None

        if not hasattr(payload, "get"):
            logger.debug(f"announce: response payload has no fields: ({payload})")
            return None

        if not payload.get("pid"):
            logger.debug(f"announce: response payload has no pid: ({payload})")
            return None

        if not payload.get("agentUuid"):
            logger.debug(f"announce: response payload has no agentUuid: ({payload})")
            return None

        return payload

    def log_message_to_host_agent(
        self,
        message: str,
    ) -> Optional[Response]:
        """
        Log a message to the discovered host agent
        """
        response = None
        try:
            payload = dict()
            payload["m"] = message

            url = self.__agent_logger_url()
            response = self.client.post(
                url,
                data=to_json(payload),
                headers={"Content-Type": "application/json", "X-Log-Level": "INFO"},
                timeout=0.8,
            )

            if 200 <= response.status_code <= 204:
                self.last_seen = datetime.now()
        except Exception as exc:
            logger.debug(f"agent logging: connection error ({type(exc)})")

    def is_agent_ready(self) -> bool:
        """
        Used after making a successful announce to test when the agent is ready to accept data.
        """
        ready = False
        try:
            response = self.client.head(self.__data_url(), timeout=0.8)

            if response.status_code == 200:
                ready = True
        except Exception as exc:
            logger.debug(f"is_agent_ready: connection error ({type(exc)})")
        return ready

    def report_data_payload(
        self,
        payload: Dict[str, Any],
    ) -> Optional[Response]:
        """
        Used to report collection payload to the host agent.  This can be metrics, spans and snapshot data.
        """
        response = None
        try:
            # Report spans (if any)
            response = self.report_spans(payload)

            if response is not None and 200 <= response.status_code <= 204:
                self.last_seen = datetime.now()

            # Report profiles (if any)
            response = self.report_profiles(payload)

            if response is not None and 200 <= response.status_code <= 204:
                self.last_seen = datetime.now()

            # Report metrics
            response = self.report_metrics(payload)

            if response is not None and 200 <= response.status_code <= 204:
                self.last_seen = datetime.now()

                if response.status_code == 200 and len(response.content) > 2:
                    # The host agent returned something indicating that is has a request for us that we
                    # need to process.
                    self.handle_agent_tasks(json.loads(response.content)[0])
        except requests.exceptions.ConnectionError:
            pass
        except urllib3.exceptions.MaxRetryError:
            pass
        except Exception as exc:
            logger.debug(
                f"report_data_payload: Instana host agent connection error ({type(exc)})",
                exc_info=True,
            )
        return response

    def report_metrics(self, payload: Dict[str, Any]) -> Optional[Response]:
        metrics = payload.get("metrics", [])
        if len(metrics) > 0:
            metric_bundle = metrics["plugins"][0]["data"]
            response = self.client.post(
                self.__data_url(),
                data=to_json(metric_bundle),
                headers={"Content-Type": "application/json"},
                timeout=0.8,
            )
            return response
        return

    def report_profiles(self, payload: Dict[str, Any]) -> Optional[Response]:
        profiles = payload.get("profiles", [])
        if len(profiles) > 0:
            logger.debug(f"Reporting {len(profiles)} profiles")
            response = self.client.post(
                self.__profiles_url(),
                data=to_json(profiles),
                headers={"Content-Type": "application/json"},
                timeout=0.8,
            )
            return response
        return

    def report_spans(self, payload: Dict[str, Any]) -> Optional[Response]:
        filtered_spans = self.filter_spans(payload.get("spans", []))
        if len(filtered_spans) > 0:
            logger.debug(f"Reporting {len(filtered_spans)} spans")
            response = self.client.post(
                self.__traces_url(),
                data=to_json(filtered_spans),
                headers={"Content-Type": "application/json"},
                timeout=0.8,
            )
            return response
        return

    def filter_spans(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filters given span list using ignore-endpoint variable and returns the list of filtered spans.
        """
        filtered_spans = []
        endpoint = ""
        for span in spans:
            if (hasattr(span, "n") or hasattr(span, "name")) and hasattr(span, "data"):
                service = span.n
                operation_specifier_key, service_specifier_key = (
                    get_operation_specifiers(service)
                )
                if service == "kafka":
                    endpoint = span.data[service][service_specifier_key]
                method = span.data[service][operation_specifier_key]
                if isinstance(method, str) and self.__is_endpoint_ignored(
                    service, method, endpoint
                ):
                    continue
                else:
                    filtered_spans.append(span)
            else:
                filtered_spans.append(span)
        return filtered_spans

    def __is_endpoint_ignored(
        self,
        service: str,
        method: str = "",
        endpoint: str = "",
    ) -> bool:
        """Check if the given service and endpoint combination should be ignored."""
        service = service.lower()
        method = method.lower()
        endpoint = endpoint.lower()
        filter_rules = [
            f"{service}.{method}",  # service.method
            f"{service}.*",  # service.*
        ]

        if service == "kafka" and endpoint:
            filter_rules += [
                f"{service}.{method}.{endpoint}",  # service.method.endpoint
                f"{service}.*.{endpoint}",  # service.*.endpoint
                f"{service}.{method}.*",  # service.method.*
            ]
        return any(rule in self.options.ignore_endpoints for rule in filter_rules)

    def handle_agent_tasks(self, task: Dict[str, Any]) -> None:
        """
        When request(s) are received by the host agent, it is sent here
        for handling & processing.
        """
        logger.debug(f"Received agent request with messageId: {task['messageId']}")
        if "action" in task:
            if task["action"] == "python.source":
                payload = get_py_source(task["args"]["file"])
            else:
                message = (
                    f"Unrecognized action: {task['action']}. An newer Instana package may be required "
                    f"for this. Current version: {VERSION}"
                )
                payload = {"error": message}
        else:
            payload = {"error": "Instana Python: No action specified in request."}

        self.__task_response(task["messageId"], payload)

    def diagnostics(self) -> None:
        """
        Helper function to dump out state.
        """
        try:
            import threading

            dt_format = "%Y-%m-%d %H:%M:%S"

            logger.warning("====> Instana Python Language Agent Diagnostics <====")

            logger.warning("----> Agent <----")
            logger.warning(f"is_agent_ready: {self.is_agent_ready()}")
            logger.warning(f"is_timed_out: {self.is_timed_out()}")
            if self.last_seen is None:
                logger.warning("last_seen: None")
            else:
                logger.warning(f"last_seen: {self.last_seen.strftime(dt_format)}")

            if self.announce_data is not None:
                logger.warning(f"announce_data: {self.announce_data.__dict__}")
            else:
                logger.warning("announce_data: None")

            logger.warning(f"Options: {self.options.__dict__}")

            logger.warning("----> StateMachine <----")
            logger.warning(f"State: {self.machine.fsm.current}")

            logger.warning("----> Collector <----")
            logger.warning(f"Collector: {self.collector}")
            logger.warning(
                f"is_collector_thread_running?: {self.collector.is_reporting_thread_running()}"
            )
            logger.warning(
                f"background_report_lock.locked?: {self.collector.background_report_lock.locked()}"
            )
            logger.warning(f"ready_to_start: {self.collector.ready_to_start}")
            logger.warning(f"reporting_thread: {self.collector.reporting_thread}")
            logger.warning(f"report_interval: {self.collector.report_interval}")
            logger.warning(
                f"should_send_snapshot_data: {self.collector.should_send_snapshot_data()}"
            )
            logger.warning(f"spans in queue: {self.collector.span_queue.qsize()}")
            logger.warning(
                f"thread_shutdown is_set: {self.collector.thread_shutdown.is_set()}"
            )

            logger.warning("----> Threads <----")
            logger.warning(f"Threads: {threading.enumerate()}")
        except Exception:
            logger.warning("Non-fatal diagnostics exception: ", exc_info=True)

    def __task_response(
        self,
        message_id: str,
        data: Dict[str, Any],
    ) -> Optional[Response]:
        """
        When the host agent passes us a task and we do it, this function is used to
        respond with the results of the task.
        """
        response = None
        try:
            payload = json.dumps(data)

            logger.debug(
                f"Task response is {self.__response_url(message_id)}: {payload}"
            )

            response = self.client.post(
                self.__response_url(message_id),
                data=payload,
                headers={"Content-Type": "application/json"},
                timeout=0.8,
            )
        except Exception as exc:
            logger.debug(
                f"__task_response: Instana host agent connection error ({type(exc)})"
            )
        return response

    def __discovery_url(self) -> str:
        """
        URL for announcing to the host agent
        """
        return f"http://{self.options.agent_host}:{self.options.agent_port}/{self.AGENT_DISCOVERY_PATH}"

    def __data_url(self) -> str:
        """
        URL for posting metrics to the host agent.  Only valid when announced.
        """
        path = self.AGENT_DATA_PATH % self.announce_data.pid
        return f"http://{self.options.agent_host}:{self.options.agent_port}/{path}"

    def __traces_url(self) -> str:
        """
        URL for posting traces to the host agent.  Only valid when announced.
        """
        path = f"com.instana.plugin.python/traces.{self.announce_data.pid}"
        return f"http://{self.options.agent_host}:{self.options.agent_port}/{path}"

    def __profiles_url(self) -> str:
        """
        URL for posting profiles to the host agent.  Only valid when announced.
        """
        path = f"com.instana.plugin.python/profiles.{self.announce_data.pid}"
        return f"http://{self.options.agent_host}:{self.options.agent_port}/{path}"

    def __response_url(self, message_id: str) -> str:
        """
        URL for responding to agent requests.
        """
        path = f"com.instana.plugin.python/response.{int(self.announce_data.pid)}?messageId={message_id}"
        return f"http://{self.options.agent_host}:{self.options.agent_port}/{path}"

    def __agent_logger_url(self) -> str:
        """
        URL for logging messages to the discovered host agent.
        """
        return f"http://{self.options.agent_host}:{self.options.agent_port}/com.instana.agent.logger"
