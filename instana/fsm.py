from __future__ import absolute_import

import os
import re
import socket
import subprocess
import sys
import threading

from fysom import Fysom

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
    THREAD_NAME = "Instana Machine"

    agent = None
    fsm = None
    timer = None

    warnedPeriodic = False

    def __init__(self, agent):
        logger.debug("Initializing host agent state machine")

        self.agent = agent
        self.fsm = Fysom({
            "events": [
                ("lookup",   "*",            "found"),
                ("announce", "found",        "announced"),
                ("pending",  "announced",    "wait4init"),
                ("ready",    "wait4init",    "good2go")],
            "callbacks": {
                # Can add the following to debug
                # "onchangestate":  self.print_state_change,
                "onlookup":       self.lookup_agent_host,
                "onannounce":     self.announce_sensor,
                "onpending":      self.on_ready}})

        self.timer = threading.Timer(1, self.fsm.lookup)
        self.timer.daemon = True
        self.timer.name = self.THREAD_NAME

        # Only start the announce process when not in Test
        if not "INSTANA_TEST" in os.environ:
            self.timer.start()

    @staticmethod
    def print_state_change(e):
        logger.debug('========= (%i#%s) FSM event: %s, src: %s, dst: %s ==========',
                     os.getpid(), threading.current_thread().name, e.event, e.src, e.dst)

    def reset(self):
        """
        reset is called to start from scratch in a process.  It may be called on first boot or
        after a detected fork.

        Here we time a new announce cycle in the future so that any existing threads have time
        to exit before we re-create them.

        :return: void
        """
        logger.debug("State machine being reset.  Will start a new announce cycle.")
        self.fsm.lookup()

    def lookup_agent_host(self, e):
        host = self.agent.options.agent_host
        port = self.agent.options.agent_port

        if self.agent.is_agent_listening(host, port):
            self.fsm.announce()
            return True

        if os.path.exists("/proc/"):
            host = get_default_gateway()
            if host:
                if self.agent.is_agent_listening(host, port):
                    self.agent.options.agent_host = host
                    self.agent.options.agent_port = port
                    self.fsm.announce()
                    return True

        if self.warnedPeriodic is False:
            logger.info("Instana Host Agent couldn't be found. Will retry periodically...")
            self.warnedPeriodic = True

        self.schedule_retry(self.lookup_agent_host, e, self.THREAD_NAME + ": agent_lookup")
        return False

    def announce_sensor(self, e):
        logger.debug("Attempting to make an announcement to the agent on %s:%d",
                     self.agent.options.agent_host, self.agent.options.agent_port)
        pid = os.getpid()

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
                (out, _) = proc.communicate()
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
            try:
                # In CentOS 7, some odd things can happen such as:
                # PermissionError: [Errno 13] Permission denied: '/proc/6/fd/8'
                # Use a try/except as a safety
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((self.agent.options.agent_host, self.agent.options.agent_port))
                path = "/proc/%d/fd/%d" % (pid, sock.fileno())
                d.fd = sock.fileno()
                d.inode = os.readlink(path)
            except:
                logger.debug("Error generating file descriptor: ", exc_info=True)

        response = self.agent.announce(d)

        if response and (response.status_code == 200) and (len(response.content) > 2):
            self.agent.set_from(response.content)
            self.fsm.pending()
            logger.debug("Announced pid: %s (true pid: %s).  Waiting for Agent Ready...",
                         str(pid), str(self.agent.announce_data.pid))
            return True

        logger.debug("Cannot announce sensor. Scheduling retry.")
        self.schedule_retry(self.announce_sensor, e, self.THREAD_NAME + ": announce")
        return False

    def schedule_retry(self, fun, e, name):
        self.timer = threading.Timer(self.RETRY_PERIOD, fun, [e])
        self.timer.daemon = True
        self.timer.name = name
        self.timer.start()

    def on_ready(self, _):
        self.agent.start()
        logger.info("Instana host agent available. We're in business. Announced pid: %s (true pid: %s)",
                    str(os.getpid()), str(self.agent.announce_data.pid))

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

        if pid is None:
            pid = os.getpid()

        return pid