import os
import sys
import socket
import subprocess
import threading as t
import fysom as f
import instana
from instana import log
import instana.agent_const as a


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


class Fsm(object):
    RETRY_PERIOD = 30

    agent = None
    fsm = None
    timer = None

    def __init__(self, agent):
        log.info("Stan is on the scene.  Starting Instana instrumentation version", instana.__version__)
        log.debug("initializing fsm")

        self.agent = agent
        self.fsm = f.Fysom({
            "events": [
                ("lookup",   "*",            "found"),
                ("announce", "found",        "announced"),
                ("ready",    "announced",    "good2go")],
            "callbacks": {
                "onlookup":       self.lookup_agent_host,
                "onannounce":     self.announce_sensor,
                "onready":        self.start_metric_reporting,
                "onchangestate":  self.printstatechange}})

        timer = t.Timer(2, self.fsm.lookup)
        timer.daemon = True
        timer.name = "Startup"
        timer.start()

    def printstatechange(self, e):
        log.debug('========= (%i#%s) FSM event: %s, src: %s, dst: %s ==========' %
                  (os.getpid(), t.current_thread().name, e.event, e.src, e.dst))

    def reset(self):
        self.fsm.lookup()

    def start_metric_reporting(self, e):
        self.agent.sensor.meter.run()

    def lookup_agent_host(self, e):
        host = a.AGENT_DEFAULT_HOST
        port = a.AGENT_DEFAULT_PORT

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

        h = self.check_host(host, port)
        if h == a.AGENT_HEADER:
            self.agent.set_host(host)
            self.agent.set_port(port)
            self.fsm.announce()
            return True
        elif os.path.exists("/proc/"):
            host = self.get_default_gateway()
            if host:
                h = self.check_host(host, port)
                if h == a.AGENT_HEADER:
                    self.agent.set_host(host)
                    self.agent.set_port(port)
                    self.fsm.announce()
                    return True

        log.info("Instana Host Agent couldn't be found. Scheduling retry.")
        self.schedule_retry(self.lookup_agent_host, e, "agent_lookup")
        return False

    def get_default_gateway(self):
        log.debug("checking default gateway")

        try:
            proc = subprocess.Popen(
                "/sbin/ip route | awk '/default/' | cut -d ' ' -f 3 | tr -d '\n'",
                shell=True, stdout=subprocess.PIPE)

            addr = proc.stdout.read()
            return addr.decode("UTF-8")
        except Exception as e:
            log.error(e)

            return None

    def check_host(self, host, port):
        log.debug("checking %s:%d" % (host, port))

        (_, h) = self.agent.request_header(
            self.agent.make_host_url(host, "/"), "GET", "Server")

        return h

    def announce_sensor(self, e):
        log.debug("announcing sensor to the agent")
        s = None
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
        except Exception as err:
            cmdline = sys.argv
            log.debug(err)

        d = Discovery(pid=pid,
                      name=cmdline[0],
                      args=cmdline[1:])

        # If we're on a system with a procfs
        if os.path.exists("/proc/"):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.agent.host, 42699))
            path = "/proc/%d/fd/%d" % (pid, s.fileno())
            d.fd = s.fileno()
            d.inode = os.readlink(path)

        (b, _) = self.agent.request_response(
            self.agent.make_url(a.AGENT_DISCOVERY_URL), "PUT", d)
        if b:
            self.agent.set_from(b)
            self.fsm.ready()
            log.info("Host agent available. We're in business. Announced pid: %i (true pid: %i)" %
                     (pid, self.agent.from_.pid))
            return True
        else:
            log.debug("Cannot announce sensor. Scheduling retry.")
            self.schedule_retry(self.announce_sensor, e, "announce")
        return False

    def schedule_retry(self, fun, e, name):
        log.debug("Scheduling: " + name)
        self.timer = t.Timer(self.RETRY_PERIOD, fun, [e])
        self.timer.daemon = True
        self.timer.name = name
        self.timer.start()
        log.debug('Threadlist: ', str(t.enumerate()))

    def test_agent(self, e):
        log.debug("testing communication with the agent")

        (b, _) = self.agent.head(self.agent.make_url(a.AGENT_DATA_URL))

        if not b:
            self.schedule_retry(self.test_agent, e, "agent test")
        else:
            self.fsm.test()
