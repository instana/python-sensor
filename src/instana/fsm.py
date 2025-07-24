# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016


import os
import re
import socket
import subprocess
import sys
import threading
from typing import TYPE_CHECKING, Any, Callable, List

from fysom import Fysom

from instana.log import logger
from instana.util import get_default_gateway
from instana.util.process_discovery import Discovery
from instana.util.runtime import is_windows
from instana.version import VERSION

if TYPE_CHECKING:
    from instana.agent.host import HostAgent


class TheMachine:
    RETRY_PERIOD = 30
    THREAD_NAME = "Instana Machine"

    warnedPeriodic = False

    def __init__(self, agent: "HostAgent") -> None:
        logger.debug("Initializing host agent state machine")

        self.agent = agent
        self.fsm = Fysom(
            {
                "events": [
                    ("lookup", "*", "found"),
                    ("announce", "found", "announced"),
                    ("pending", "announced", "wait4init"),
                    ("ready", "wait4init", "good2go"),
                ],
                "callbacks": {
                    # Can add the following to debug
                    # "onchangestate":  self.print_state_change,
                    "onlookup": self.lookup_agent_host,
                    "onannounce": self.announce_sensor,
                    "onpending": self.on_ready,
                    "ongood2go": self.on_good2go,
                },
            }
        )

        self.timer = threading.Timer(1, self.fsm.lookup)
        self.timer.daemon = True
        self.timer.name = self.THREAD_NAME
        self.timer.start()

    @staticmethod
    def print_state_change(e: Any) -> None:
        logger.debug(
            f"========= ({os.getpid()}#{threading.current_thread().name}) FSM event: {e.event}, src: {e.src}, dst: {e.dst} =========="
        )

    def reset(self) -> None:
        """
        reset is called to start from scratch in a process.  It may be called on first boot or
        after a detected fork.

        Here we time a new announce cycle in the future so that any existing threads have time
        to exit before we re-create them.

        :return: void
        """
        logger.debug("State machine being reset.  Will start a new announce cycle.")
        self.fsm.lookup()

    def lookup_agent_host(self, e: Any) -> bool:
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
            logger.info(
                "Instana Host Agent couldn't be found. Will retry periodically..."
            )
            self.warnedPeriodic = True

        self.schedule_retry(
            self.lookup_agent_host, e, f"{self.THREAD_NAME}: agent_lookup"
        )
        return False

    def announce_sensor(self, e: Any) -> bool:
        pid: int = os.getpid()
        logger.debug(
            f"Attempting to announce PID {pid} to the agent on {self.agent.options.agent_host}:{self.agent.options.agent_port}"
        )

        cmdline = self._get_cmdline(pid)

        d = Discovery(pid=self.__get_real_pid(), name=cmdline[0], args=cmdline[1:])

        self._setup_socket_connection(d, pid)

        payload = self.agent.announce(d)

        if not payload:
            logger.debug("Cannot announce sensor. Scheduling retry.")
            self.schedule_retry(
                self.announce_sensor, e, f"{self.THREAD_NAME}: announce"
            )
            return False

        self.agent.set_from(payload)
        self.fsm.pending()
        logger.debug(
            f"Announced PID: {pid} (true PID: {self.agent.announce_data.pid}).  Waiting for Agent Ready..."
        )
        return True

    def schedule_retry(self, fun: Callable, e: Any, name: str) -> None:
        self.timer = threading.Timer(self.RETRY_PERIOD, fun, [e])
        self.timer.daemon = True
        self.timer.name = name
        self.timer.start()

    def on_ready(self, _: Any) -> None:
        self.agent.start()

        ns_pid = str(os.getpid())
        true_pid = str(self.agent.announce_data.pid)

        logger.info(
            f"Instana host agent available. We're in business. Announced PID: {ns_pid} (true PID: {true_pid})"
        )

    def on_good2go(self, _: Any) -> None:
        ns_pid = str(os.getpid())
        true_pid = str(self.agent.announce_data.pid)

        self.agent.log_message_to_host_agent(
            f"Instana Python Package {VERSION}: PID {ns_pid} (true PID: {true_pid}) is now online and reporting"
        )

    def __get_real_pid(self) -> int:
        """
        Attempts to determine the true process ID by querying the
        /proc/<pid>/sched file on Linux systems or using the OS default PID.
        For Windows, we use the standard OS PID as there's no equivalent concept
        of container PIDs vs host PIDs.
        """
        pid = None

        # For Linux systems with procfs
        if os.path.exists("/proc/"):
            sched_file = f"/proc/{os.getpid()}/sched"

            if os.path.isfile(sched_file):
                try:
                    with open(sched_file) as file:
                        line = file.readline()
                        g = re.search(r"\((\d+),", line)
                        if g and len(g.groups()) == 1:
                            pid = int(g.groups()[0])
                except Exception:
                    logger.debug("parsing sched file failed", exc_info=True)

        # For Windows or if Linux method failed
        if pid is None:
            pid = os.getpid()

        return pid

    def _get_cmdline_windows(self) -> List[str]:
        """
        Get command line using Windows API
        """
        import ctypes
        from ctypes import wintypes

        GetCommandLineW = ctypes.windll.kernel32.GetCommandLineW
        GetCommandLineW.argtypes = []
        GetCommandLineW.restype = wintypes.LPCWSTR

        cmd = GetCommandLineW()
        # Simple parsing - this is a basic approach and might need refinement
        # for complex command lines with quotes and spaces
        return cmd.split()

    def _get_cmdline_linux_proc(self) -> List[str]:
        """
        Get command line from Linux /proc filesystem
        """
        with open("/proc/self/cmdline") as cmd:
            cmdinfo = cmd.read()
        return cmdinfo.split("\x00")

    def _get_cmdline_unix_ps(self, pid: int) -> List[str]:
        """
        Get command line using ps command (for Unix-like systems without /proc)
        """
        proc = subprocess.Popen(
            ["ps", "-p", str(pid), "-o", "command"], stdout=subprocess.PIPE
        )
        (out, _) = proc.communicate()
        parts = out.split(b"\n")
        return [parts[1].decode("utf-8")]

    def _get_cmdline_unix(self, pid: int) -> List[str]:
        """
        Get command line using Unix
        """
        if os.path.isfile("/proc/self/cmdline"):
            return self._get_cmdline_linux_proc()
        else:
            return self._get_cmdline_unix_ps(pid)

    def _get_cmdline(self, pid: int) -> List[str]:
        """
        Get command line in a platform-independent way
        """
        try:
            if is_windows():
                return self._get_cmdline_windows()
            else:
                return self._get_cmdline_unix(pid)
        except Exception:
            logger.debug("Error getting command line", exc_info=True)
            return sys.argv

    def _setup_socket_connection(self, discovery: Discovery, pid: int) -> None:
        """
        Set up socket connection and populate discovery object with socket details
        """
        try:
            # In CentOS 7, some odd things can happen such as:
            # PermissionError: [Errno 13] Permission denied: '/proc/6/fd/8'
            # Use a try/except as a safety
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.agent.options.agent_host, self.agent.options.agent_port))
            discovery.fd = sock.fileno()

            # If we're on a system with a procfs (Linux)
            if os.path.exists("/proc/"):
                try:
                    path = "/proc/%d/fd/%d" % (pid, sock.fileno())
                    discovery.inode = os.readlink(path)
                except Exception:
                    logger.debug(
                        "Error generating file descriptor inode: ", exc_info=True
                    )
        except Exception:
            logger.debug("Error creating socket connection: ", exc_info=True)


# Made with Bob
