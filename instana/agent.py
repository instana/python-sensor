from __future__ import absolute_import

import json
import os
from datetime import datetime
import threading
import requests

import instana.singletons

from .agent_const import (AGENT_DATA_PATH, AGENT_DEFAULT_HOST,
                          AGENT_DEFAULT_PORT, AGENT_DISCOVERY_PATH,
                          AGENT_HEADER, AGENT_RESPONSE_PATH, AGENT_TRACES_PATH)
from .fsm import TheMachine
from .log import logger
from .sensor import Sensor


class From(object):
    pid = ""
    agentUuid = ""

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class Agent(object):
    """
    The Agent class is the central controlling entity for the Instana Python language sensor.  The key
    parts it handles are the announce state and the collection and reporting of metrics and spans to the
    Instana Host agent.

    To do this, there are 3 major components to this class:
      1. TheMachine - finite state machine related to announce state
      2. Sensor -> Meter - metric collection and reporting
      3. Tracer -> Recorder - span queueing and reporting
    """
    sensor = None
    host = AGENT_DEFAULT_HOST
    port = AGENT_DEFAULT_PORT
    machine = None
    from_ = From()
    last_seen = None
    last_fork_check = None
    _boot_pid = os.getpid()
    extra_headers = None
    secrets_matcher = 'contains-ignore-case'
    secrets_list = ['key', 'password', 'secret']
    client = requests.Session()
    should_threads_shutdown = threading.Event()

    def __init__(self):
        logger.debug("initializing agent")
        self.sensor = Sensor(self)
        self.machine = TheMachine(self)

    def start(self, _):
        """
        Starts the agent and required threads

        This method is called after a successful announce.  See fsm.py
        """
        logger.debug("Spawning metric & span reporting threads")
        self.should_threads_shutdown.clear()
        self.sensor.start()
        instana.singletons.tracer.recorder.start()

    def handle_fork(self):
        """
        Forks happen.  Here we handle them.  Affected components are the singletons: Agent, Sensor & Tracers
        """
        # Reset the Agent
        self.reset()

    def reset(self):
        """
        This will reset the agent to a fresh unannounced state.
        :return: None
        """
        # Will signal to any running background threads to shutdown.
        self.should_threads_shutdown.set()

        self.last_seen = None
        self.from_ = From()

        # Will schedule a restart of the announce cycle in the future
        self.machine.reset()

    def to_json(self, o):
        def extractor(o):
            return {k.lower(): v for k, v in o.__dict__.items() if v is not None}

        try:
            return json.dumps(o, default=extractor, sort_keys=False, separators=(',', ':')).encode()
        except Exception:
            logger.debug("to_json", exc_info=True)

    def is_timed_out(self):
        if self.last_seen and self.can_send:
            diff = datetime.now() - self.last_seen
            if diff.seconds > 60:
                return True
        return False

    def can_send(self):
        # Watch for pid change (fork)
        current_pid = os.getpid()
        if self._boot_pid != current_pid:
            self._boot_pid = current_pid
            logger.debug("Fork detected; Handling like a pro...")
            self.handle_fork()
            return False

        if self.machine.fsm.current == "good2go":
            return True

        return False

    def set_from(self, json_string):
        if type(json_string) is bytes:
            raw_json = json_string.decode("UTF-8")
        else:
            raw_json = json_string

        res_data = json.loads(raw_json)

        if "secrets" in res_data:
            self.secrets_matcher = res_data['secrets']['matcher']
            self.secrets_list = res_data['secrets']['list']

        if "extraHeaders" in res_data:
            self.extra_headers = res_data['extraHeaders']
            logger.info("Will also capture these custom headers: %s", self.extra_headers)

        self.from_ = From(pid=res_data['pid'], agentUuid=res_data['agentUuid'])

    def is_agent_listening(self, host, port):
        """
        Check if the Instana Agent is listening on <host> and <port>.
        """
        try:
            rv = False
            url = "http://%s:%s/" % (host, port)
            response = self.client.get(url, timeout=0.8)

            server_header = response.headers["Server"]
            if server_header == AGENT_HEADER:
                logger.debug("Host agent found on %s:%d", host, port)
                rv = True
            else:
                logger.debug("...something is listening on %s:%d but it's not the Instana Host Agent: %s",
                             host, port, server_header)
        except (requests.ConnectTimeout, requests.ConnectionError):
            logger.debug("Instana Host Agent not found on %s:%d", host, port)
            rv = False
        finally:
            return rv

    def announce(self, discovery):
        """
        With the passed in Discovery class, attempt to announce to the host agent.
        """
        try:
            url = self.__discovery_url()
            logger.debug("making announce request to %s", url)
            response = None
            response = self.client.put(url,
                                       data=self.to_json(discovery),
                                       headers={"Content-Type": "application/json"},
                                       timeout=0.8)

            if response.status_code is 200:
                self.last_seen = datetime.now()
        except (requests.ConnectTimeout, requests.ConnectionError):
            logger.debug("announce", exc_info=True)
        finally:
            return response

    def is_agent_ready(self):
        """
        Used after making a successful announce to test when the agent is ready to accept data.
        """
        try:
            response = self.client.head(self.__data_url(), timeout=0.8)

            if response.status_code is 200:
                return True
            return False
        except (requests.ConnectTimeout, requests.ConnectionError):
            logger.debug("is_agent_ready: host agent connection error")

    def report_data(self, entity_data):
        """
        Used to report entity data (metrics & snapshot) to the host agent.
        """
        try:
            response = None
            response = self.client.post(self.__data_url(),
                                        data=self.to_json(entity_data),
                                        headers={"Content-Type": "application/json"},
                                        timeout=0.8)

            # logger.warn("report_data: response.status_code is %s" % response.status_code)

            if response.status_code is 200:
                self.last_seen = datetime.now()
        except (requests.ConnectTimeout, requests.ConnectionError):
            logger.debug("report_data: host agent connection error")
        finally:
            return response

    def report_traces(self, spans):
        """
        Used to report entity data (metrics & snapshot) to the host agent.
        """
        try:
            response = None
            response = self.client.post(self.__traces_url(),
                                        data=self.to_json(spans),
                                        headers={"Content-Type": "application/json"},
                                        timeout=0.8)

            # logger.warn("report_traces: response.status_code is %s" % response.status_code)

            if response.status_code is 200:
                self.last_seen = datetime.now()
        except (requests.ConnectTimeout, requests.ConnectionError):
            logger.debug("report_traces: host agent connection error")
        finally:
            return response

    def task_response(self, message_id, data):
        """
        When the host agent passes us a task and we do it, this function is used to
        respond with the results of the task.
        """
        try:
            response = None
            payload = json.dumps(data)

            logger.debug("Task response is %s: %s", self.__response_url(message_id), payload)

            response = self.client.post(self.__response_url(message_id),
                                        data=payload,
                                        headers={"Content-Type": "application/json"},
                                        timeout=0.8)
        except (requests.ConnectTimeout, requests.ConnectionError):
            logger.debug("task_response", exc_info=True)
        except Exception:
            logger.debug("task_response Exception", exc_info=True)
        finally:
            return response

    def __discovery_url(self):
        """
        URL for announcing to the host agent
        """
        port = self.sensor.options.agent_port
        if port == 0:
            port = AGENT_DEFAULT_PORT

        return "http://%s:%s/%s" % (self.host, port, AGENT_DISCOVERY_PATH)

    def __data_url(self):
        """
        URL for posting metrics to the host agent.  Only valid when announced.
        """
        path = AGENT_DATA_PATH % self.from_.pid
        return "http://%s:%s/%s" % (self.host, self.port, path)

    def __traces_url(self):
        """
        URL for posting traces to the host agent.  Only valid when announced.
        """
        path = AGENT_TRACES_PATH % self.from_.pid
        return "http://%s:%s/%s" % (self.host, self.port, path)

    def __response_url(self, message_id):
        """
        URL for responding to agent requests.
        """
        if self.from_.pid != 0:
            path = AGENT_RESPONSE_PATH % (self.from_.pid, message_id)

        return "http://%s:%s/%s" % (self.host, self.port, path)
