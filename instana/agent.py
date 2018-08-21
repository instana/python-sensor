from __future__ import absolute_import

import json
import os
import threading
from datetime import datetime

import instana.singletons

from .agent_const import AGENT_DEFAULT_HOST, AGENT_DEFAULT_PORT
from .fsm import Fsm
from .log import logger
from .sensor import Sensor

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2


class From(object):
    pid = ""
    agentUuid = ""

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class Head(urllib2.Request):

    def get_method(self):
        return "HEAD"


class Put(urllib2.Request):

    def get_method(self):
        return "PUT"


class Agent(object):
    sensor = None
    host = AGENT_DEFAULT_HOST
    port = AGENT_DEFAULT_PORT
    fsm = None
    from_ = From()
    last_seen = None
    last_fork_check = None
    _boot_pid = os.getpid()

    def __init__(self):
        logger.debug("initializing agent")
        self.sensor = Sensor(self)
        self.fsm = Fsm(self)

    def start(self, e):
        """ Starts the agent and required threads """
        logger.debug("Spawning metric & trace reporting threads")
        self.sensor.meter.run()
        instana.singletons.tracer.recorder.run()

    def to_json(self, o):
        try:
            return json.dumps(o, default=lambda o: {k.lower(): v for k, v in o.__dict__.items()},
                              sort_keys=False, separators=(',', ':')).encode()
        except Exception as e:
            logger.info("to_json: ", e, o)

    def is_timed_out(self):
        if self.last_seen and self.can_send:
            diff = datetime.now() - self.last_seen
            if diff.seconds > 60:
                return True
        return False

    def can_send(self):
        # Watch for pid change in the case of ; if so, re-announce
        current_pid = os.getpid()
        if self._boot_pid != current_pid:
            self._boot_pid = current_pid
            self.handle_fork()
            return False

        if (self.fsm.fsm.current == "good2go"):
            return True

        return False

    def head(self, url):
        return self.request(url, "HEAD", None)

    def request(self, url, method, o):
        return self.full_request_response(url, method, o, False, "")

    def request_response(self, url, method, o):
        return self.full_request_response(url, method, o, True, "")

    def request_header(self, url, method, header):
        return self.full_request_response(url, method, None, False, header)

    def full_request_response(self, url, method, o, body, header):
        b = None
        h = None
        try:
            if method == "HEAD":
                request = Head(url)
            elif method == "GET":
                request = urllib2.Request(url)
            elif method == "PUT":
                request = Put(url, self.to_json(o))
                request.add_header("Content-Type", "application/json")
            else:
                request = urllib2.Request(url, self.to_json(o))
                request.add_header("Content-Type", "application/json")

            response = urllib2.urlopen(request, timeout=2)

            if not response:
                self.reset()
            else:
                if response.getcode() < 200 or response.getcode() >= 300:
                    logger.error("Request returned erroneous code", response.getcode())
                    if self.can_send():
                        self.reset()
                else:
                    self.last_seen = datetime.now()
                    if body:
                        b = response.read()

                    if header:
                        h = response.info().get(header)

                    if method == "HEAD":
                        b = True
                    # logger.warn("%s %s --> response: %s" % (method, url, b))
        except Exception as e:
            # No need to show the initial 404s or timeouts.  The agent
            # should handle those correctly.
            if not (type(e) is urllib2.HTTPError and e.code == 404):
                logger.debug("%s: full_request_response: %s" %
                             (threading.current_thread().name, str(e)))

        return (b, h)

    def make_url(self, prefix):
        return self.make_host_url(self.host, prefix)

    def make_host_url(self, host, prefix):
        port = self.sensor.options.agent_port
        if port == 0:
            port = AGENT_DEFAULT_PORT

        return self.make_full_url(host, port, prefix)

    def make_full_url(self, host, port, prefix):
        s = "http://%s:%s%s" % (host, str(port), prefix)
        if self.from_.pid != 0:
            s = "%s%s" % (s, self.from_.pid)

        return s

    def set_from(self, json_string):
        if type(json_string) is bytes:
            raw_json = json_string.decode("UTF-8")
        else:
            raw_json = json_string

        self.from_ = From(**json.loads(raw_json))

    def reset(self):
        self.last_seen = None
        self.from_ = From()
        self.fsm.reset()

    def handle_fork(self):
        self.reset()
        self.sensor.handle_fork()
        instana.singletons.tracer.handle_fork()
