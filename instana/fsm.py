from __future__ import absolute_import

import os
import re
import socket
import subprocess
import sys
import threading as t

from fysom import Fysom
import pkg_resources

from .agent_const import AGENT_DEFAULT_HOST, AGENT_DEFAULT_PORT
from .log import logger
from .util import get_default_gateway


class Discovery(object):
    pid = 0
    name = None
    args = None
    fd = -1
    inode = ""

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def to_dict(self):
        kvs = dict()
        kvs['pid'] = self.pid
        kvs['name'] = self.name
        kvs['args'] = self.args
        kvs['fd'] = self.fd
        kvs['inode'] = self.inode
        return kvs


class TheMachine(object):
    RETRY_PERIOD = 30

    agent = None
    fsm = None
    timer = None

    warnedPeriodic = False

    def __init__(self, agent):
        package_version = 'unknown'
        try:
            package_version = pkg_resources.get_distribution('instana').version
        except pkg_resources.DistributionNotFound:
            pass

        logger.info("Stan is on the scene.  Starting Instana instrumentation version: %s" % package_version)
        logger.debug("initializing fsm")

        self.agent = agent
        self.fsm = Fysom({
            "events": [
                ("lookup",   "*",            "found"),
                ("announce", "found",        "announced"),
                ("pending",  "announced",    "wait4init"),
                ("ready",    "wait4init",    "good2go")],
            "callbacks": {
                "onlookup":       self.lookup_agent_host,
                "onannounce":     self.announce_sensor,
                "onpending":      self.agent.start,
                "onready":        self.on_ready,
                "onchangestate":  self.printstatechange}})

        self.timer = t.Timer(5, self.fsm.lookup)
        self.timer.daemon = True
        self.timer.name = "Startup"
        self.timer.start()

    def printstatechange(self, e):
        logger.debug('========= (%i#%s) FSM event: %s, src: %s, dst: %s ==========' %
                     (os.getpid(), t.current_thread().name, e.event, e.src, e.dst))

    def reset(self):
        self.fsm.lookup()

    def lookup_agent_host(self, e):
        host, port = self.__get_agent_host_port()

        if self.agent.is_agent_listening(host, port):
            self.agent.host = host
            self.agent.port = port
            self.fsm.announce()
            return True
        elif os.path.exists("/proc/"):
            host = get_default_gateway()
            if host:
                if self.agent.is_agent_listening(host, port):
                    self.agent.host = host
                    self.agent.port = port
                    self.fsm.announce()
                    return True

        if self.warnedPeriodic is False:
            logger.warn("Instana Host Agent couldn't be found. Will retry periodically...")
            self.warnedPeriodic = True

        self.schedule_retry(self.lookup_agent_host, e, "agent_lookup")
        return False

    def announce_sensor(self, e):
        logger.debug("Announcing sensor to the agent")
        sock = None
        pid = os.getpid()
        cmdline = []

        try:
            if os.path.isfile("/proc/self/cmdline"):
                with open("/proc/self/cmdline") as cmd:
                    cmdinfo = cmd.read()
                cmdline = cmdinfo.split('\x00')
            else:
                # Python doesn't provide a reliable method to determine what
                # the OS process command line may be.  Here we are forced to
                # rely on ps rather than adding a dependency on something like
                # psutil which requires dev packages, gcc etc...
                proc = subprocess.Popen(["ps", "-p", str(pid), "-o", "command"],
                                        stdout=subprocess.PIPE)
                (out, err) = proc.communicate()
                parts = out.split(b'\n')
                cmdline = [parts[1].decode("utf-8")]
        except Exception:
            cmdline = sys.argv
            logger.debug("announce_sensor", exc_info=True)

        d = Discovery(pid=self.__get_real_pid(),
                      name=cmdline[0],
                      args=cmdline[1:])

        # If we're on a system with a procfs
        if os.path.exists("/proc/"):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.agent.host, 42699))
            path = "/proc/%d/fd/%d" % (pid, sock.fileno())
            d.fd = sock.fileno()
            d.inode = os.readlink(path)

        response = self.agent.announce(d)

        if response and (response.status_code is 200) and (len(response.content) > 2):
            self.agent.set_from(response.content)
            self.fsm.pending()
            logger.debug("Announced pid: %s (true pid: %s).  Waiting for Agent Ready..." % (str(pid), str(self.agent.from_.pid)))
            return True
        else:
            logger.debug("Cannot announce sensor. Scheduling retry.")
            self.schedule_retry(self.announce_sensor, e, "announce")
        return False

    def schedule_retry(self, fun, e, name):
        self.timer = t.Timer(self.RETRY_PERIOD, fun, [e])
        self.timer.daemon = True
        self.timer.name = name
        self.timer.start()

    def on_ready(self, e):
        logger.info("Host agent available. We're in business. Announced pid: %s (true pid: %s)" %
                    (str(os.getpid()), str(self.agent.from_.pid)))

    def __get_real_pid(self):
        """
        Attempts to determine the true process ID by querying the
        /proc/<pid>/sched file.  This works on systems with a proc filesystem.
        Otherwise default to os default.
        """
        pid = None

        if os.path.exists("/proc/"):
            sched_file = "/proc/%d/sched" % os.getpid()

            if os.path.isfile(sched_file):
                try:
                    file = open(sched_file)
                    line = file.readline()
                    g = re.search(r'\((\d+),', line)
                    if len(g.groups()) == 1:
                        pid = int(g.groups()[0])
                except Exception:
                    logger.debug("parsing sched file failed", exc_info=True)
                    pass

        if pid is None:
            pid = os.getpid()

        return pid

    def __get_agent_host_port(self):
        """
        Iterates the the various ways the host and port of the Instana host
        agent may be configured: default, env vars, sensor options...
        """
        host = AGENT_DEFAULT_HOST
        port = AGENT_DEFAULT_PORT

        if "INSTANA_AGENT_HOST" in os.environ:
            host = os.environ["INSTANA_AGENT_HOST"]
            if "INSTANA_AGENT_PORT" in os.environ:
                port = int(os.environ["INSTANA_AGENT_PORT"])

        elif "INSTANA_AGENT_IP" in os.environ:
            # Deprecated: INSTANA_AGENT_IP environment variable
            # To be removed in a future version
            host = os.environ["INSTANA_AGENT_IP"]
            if "INSTANA_AGENT_PORT" in os.environ:
                port = int(os.environ["INSTANA_AGENT_PORT"])

        elif self.agent.sensor.options.agent_host != "":
            host = self.agent.sensor.options.agent_host
            if self.agent.sensor.options.agent_port != 0:
                port = self.agent.sensor.options.agent_port

        return host, port
