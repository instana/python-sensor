# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
The in-process Instana agent (for host based processes) that manages
monitoring state and reporting that data.
"""
from __future__ import absolute_import

import os
import json
from datetime import datetime

import urllib3
import requests

from ..log import logger
from .base import BaseAgent
from ..fsm import TheMachine
from ..version import VERSION
from ..options import StandardOptions
from ..collector.host import HostCollector
from ..util import to_json
from ..util.runtime import get_py_source


class AnnounceData(object):
    """ The Announce Payload """
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
    AGENT_HEADER = "Instana Agent"

    def __init__(self):
        super(HostAgent, self).__init__()

        self.announce_data = None
        self.machine = None
        self.last_seen = None
        self.last_fork_check = None
        self._boot_pid = os.getpid()
        self.options = StandardOptions()

        # Update log level from what Options detected
        self.update_log_level()

        logger.info("Stan is on the scene.  Starting Instana instrumentation version: %s", VERSION)

        self.collector = HostCollector(self)
        self.machine = TheMachine(self)

    def start(self):
        """
        Starts the agent and required threads

        This method is called after a successful announce.  See fsm.py
        """
        logger.debug("Starting Host Collector")
        self.collector.start()

    def handle_fork(self):
        """
        Forks happen.  Here we handle them.
        """
        # Reset the Agent
        self.reset()

    def reset(self):
        """
        This will reset the agent to a fresh unannounced state.
        :return: None
        """
        self.last_seen = None
        self.announce_data = None
        self.collector.shutdown(report_final=False)

        # Will schedule a restart of the announce cycle in the future
        self.machine.reset()

    def is_timed_out(self):
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

    def can_send(self):
        """
        Are we in a state where we can send data?
        @return: Boolean
        """
        if "INSTANA_TEST" in os.environ:
            return True

        # Watch for pid change (fork)
        self.last_fork_check = datetime.now()
        current_pid = os.getpid()
        if self._boot_pid != current_pid:
            self._boot_pid = current_pid
            logger.debug("Fork detected; Handling like a pro...")
            self.handle_fork()
            return False

        if self.machine.fsm.current in ["wait4init", "good2go"]:
            return True

        return False

    def set_from(self, json_string):
        """
        Sets the source identifiers given to use by the Instana Host agent.
        @param json_string: source identifiers
        @return: None
        """
        if isinstance(json_string, bytes):
            raw_json = json_string.decode("UTF-8")
        else:
            raw_json = json_string

        res_data = json.loads(raw_json)

        if "secrets" in res_data:
            self.options.secrets_matcher = res_data['secrets']['matcher']
            self.options.secrets_list = res_data['secrets']['list']

        if "extraHeaders" in res_data:
            if self.options.extra_http_headers is None:
                self.options.extra_http_headers = res_data['extraHeaders']
            else:
                self.options.extra_http_headers.extend(res_data['extraHeaders'])
            logger.info("Will also capture these custom headers: %s", self.options.extra_http_headers)

        self.announce_data = AnnounceData(pid=res_data['pid'], agentUuid=res_data['agentUuid'])

    def get_from_structure(self):
        """
        Retrieves the From data that is reported alongside monitoring data.
        @return: dict()
        """
        return {'e': self.announce_data.pid, 'h': self.announce_data.agentUuid}

    def is_agent_listening(self, host, port):
        """
        Check if the Instana Agent is listening on <host> and <port>.
        @return: Boolean
        """
        result = False
        try:
            url = "http://%s:%s/" % (host, port)
            response = self.client.get(url, timeout=0.8)

            server_header = response.headers["Server"]
            if server_header == self.AGENT_HEADER:
                logger.debug("Instana host agent found on %s:%d", host, port)
                result = True
            else:
                logger.debug("...something is listening on %s:%d but it's not the Instana Host Agent: %s",
                             host, port, server_header)
        except Exception:
            logger.debug("Instana Host Agent not found on %s:%d", host, port)
        return result

    def announce(self, discovery):
        """
        With the passed in Discovery class, attempt to announce to the host agent.
        """
        response = None
        try:
            url = self.__discovery_url()
            response = self.client.put(url,
                                       data=to_json(discovery),
                                       headers={"Content-Type": "application/json"},
                                       timeout=0.8)

            if 200 <= response.status_code <= 204:
                self.last_seen = datetime.now()
        except Exception as exc:
            logger.debug("announce: connection error (%s)", type(exc))
        return response

    def log_message_to_host_agent(self, message):
        """
        Log a message to the discovered host agent
        """
        response = None
        try:
            payload = dict()
            payload["m"] = message

            url = self.__agent_logger_url()
            response = self.client.post(url,
                                       data=to_json(payload),
                                       headers={"Content-Type": "application/json",
                                                "X-Log-Level": "INFO"},
                                       timeout=0.8)

            if 200 <= response.status_code <= 204:
                self.last_seen = datetime.now()
        except Exception as exc:
            logger.debug("agent logging: connection error (%s)", type(exc))

    def is_agent_ready(self):
        """
        Used after making a successful announce to test when the agent is ready to accept data.
        """
        ready = False
        try:
            response = self.client.head(self.__data_url(), timeout=0.8)

            if response.status_code == 200:
                ready = True
        except Exception as exc:
            logger.debug("is_agent_ready: connection error (%s)", type(exc))
        return ready

    def report_data_payload(self, payload):
        """
        Used to report collection payload to the host agent.  This can be metrics, spans and snapshot data.
        """
        response = None
        try:
            # Report spans (if any)
            span_count = len(payload['spans'])
            if span_count > 0:
                logger.debug("Reporting %d spans", span_count)
                response = self.client.post(self.__traces_url(),
                                            data=to_json(payload['spans']),
                                            headers={"Content-Type": "application/json"},
                                            timeout=0.8)

            if response is not None and 200 <= response.status_code <= 204:
                self.last_seen = datetime.now()

            # Report profiles (if any)
            profile_count = len(payload['profiles'])
            if profile_count > 0:
                logger.debug("Reporting %d profiles", profile_count)
                response = self.client.post(self.__profiles_url(),
                                            data=to_json(payload['profiles']),
                                            headers={"Content-Type": "application/json"},
                                            timeout=0.8)

            if response is not None and 200 <= response.status_code <= 204:
                self.last_seen = datetime.now()

            # Report metrics
            metric_bundle = payload["metrics"]["plugins"][0]["data"]
            response = self.client.post(self.__data_url(),
                                        data=to_json(metric_bundle),
                                        headers={"Content-Type": "application/json"},
                                        timeout=0.8)

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
            logger.debug("report_data_payload: Instana host agent connection error (%s)", type(exc), exc_info=True)
        return response

    def handle_agent_tasks(self, task):
        """
        When request(s) are received by the host agent, it is sent here
        for handling & processing.
        """
        logger.debug("Received agent request with messageId: %s", task["messageId"])
        if "action" in task:
            if task["action"] == "python.source":
                payload = get_py_source(task["args"]["file"])
            else:
                message = "Unrecognized action: %s. An newer Instana package may be required " \
                          "for this. Current version: %s" % (task["action"], VERSION)
                payload = {"error": message}
        else:
            payload = {"error": "Instana Python: No action specified in request."}

        self.__task_response(task["messageId"], payload)


    def diagnostics(self):
        """
        Helper function to dump out state.
        """
        try:
            import threading
            dt_format = "%Y-%m-%d %H:%M:%S"

            logger.warning("====> Instana Python Language Agent Diagnostics <====")

            logger.warning("----> Agent <----")
            logger.warning("is_agent_ready: %s", self.is_agent_ready())
            logger.warning("is_timed_out: %s", self.is_timed_out())
            if self.last_seen is None:
                logger.warning("last_seen: None")
            else:
                logger.warning("last_seen: %s", self.last_seen.strftime(dt_format))

            if self.announce_data is not None:
                logger.warning("announce_data: %s", self.announce_data.__dict__)
            else:
                logger.warning("announce_data: None")

            logger.warning("Options: %s", self.options.__dict__)

            logger.warning("----> StateMachine <----")
            logger.warning("State: %s", self.machine.fsm.current)

            logger.warning("----> Collector <----")
            logger.warning("Collector: %s", self.collector)
            logger.warning("is_collector_thread_running?: %s", self.collector.is_reporting_thread_running())
            logger.warning("background_report_lock.locked?: %s", self.collector.background_report_lock.locked())
            logger.warning("ready_to_start: %s", self.collector.ready_to_start)
            logger.warning("reporting_thread: %s", self.collector.reporting_thread)
            logger.warning("report_interval: %s", self.collector.report_interval)
            logger.warning("should_send_snapshot_data: %s", self.collector.should_send_snapshot_data())
            logger.warning("spans in queue: %s", self.collector.span_queue.qsize())
            logger.warning("thread_shutdown is_set: %s", self.collector.thread_shutdown.is_set())

            logger.warning("----> Threads <----")
            logger.warning("Threads: %s", threading.enumerate())
        except Exception:
            logger.warning("Non-fatal diagnostics exception: ", exc_info=True)

    def __task_response(self, message_id, data):
        """
        When the host agent passes us a task and we do it, this function is used to
        respond with the results of the task.
        """
        response = None
        try:
            payload = json.dumps(data)

            logger.debug("Task response is %s: %s", self.__response_url(message_id), payload)

            response = self.client.post(self.__response_url(message_id),
                                        data=payload,
                                        headers={"Content-Type": "application/json"},
                                        timeout=0.8)
        except Exception as exc:
            logger.debug("__task_response: Instana host agent connection error (%s)", type(exc))
        return response

    def __discovery_url(self):
        """
        URL for announcing to the host agent
        """
        return "http://%s:%s/%s" % (self.options.agent_host, self.options.agent_port, self.AGENT_DISCOVERY_PATH)

    def __data_url(self):
        """
        URL for posting metrics to the host agent.  Only valid when announced.
        """
        path = self.AGENT_DATA_PATH % self.announce_data.pid
        return "http://%s:%s/%s" % (self.options.agent_host, self.options.agent_port, path)

    def __traces_url(self):
        """
        URL for posting traces to the host agent.  Only valid when announced.
        """
        path = "com.instana.plugin.python/traces.%d" % self.announce_data.pid
        return "http://%s:%s/%s" % (self.options.agent_host, self.options.agent_port, path)

    def __profiles_url(self):
        """
        URL for posting profiles to the host agent.  Only valid when announced.
        """
        path = "com.instana.plugin.python/profiles.%d" % self.announce_data.pid
        return "http://%s:%s/%s" % (self.options.agent_host, self.options.agent_port, path)

    def __response_url(self, message_id):
        """
        URL for responding to agent requests.
        """
        path = "com.instana.plugin.python/response.%d?messageId=%s" % (int(self.announce_data.pid), message_id)
        return "http://%s:%s/%s" % (self.options.agent_host, self.options.agent_port, path)

    def __agent_logger_url(self):
        """
        URL for logging messages to the discovered host agent.
        """
        return "http://%s:%s/%s" % (self.options.agent_host, self.options.agent_port, "com.instana.agent.logger")
