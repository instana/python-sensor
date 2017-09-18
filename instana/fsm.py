import subprocess
import os
import psutil
import socket
import threading as t
import fysom as f
import instana.log as l
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
        l.info("Stan is on the scene.  Starting Instana instrumentation.")
        l.debug("initializing fsm")

        self.agent = agent
        self.fsm = f.Fysom({
            "initial": "lostandalone",
            "events": [
                ("startup",  "*",            "lostandalone"),
                ("lookup",   "lostandalone", "found"),
                ("announce", "found",        "announced"),
                ("ready",    "announced",    "good2go")],
            "callbacks": {
                "onlookup":       self.lookup_agent_host,
                "onannounce":     self.announce_sensor,
                "onchangestate":  self.printstatechange}})

    def printstatechange(self, e):
        l.debug('========= (%i#%s) FSM event: %s, src: %s, dst: %s ==========' % \
                (os.getpid(), t.current_thread().name, e.event, e.src, e.dst))

    def reset(self):
        self.fsm.lookup()

    def lookup_agent_host(self, e):
        if self.agent.sensor.options.agent_host != "":
            host = self.agent.sensor.options.agent_host
        else:
            host = a.AGENT_DEFAULT_HOST

        h = self.check_host(host)
        if h == a.AGENT_HEADER:
            self.agent.set_host(host)
            self.fsm.announce()
            return True
        elif os.path.exists("/proc/"):
            host = self.get_default_gateway()
            if host:
                h = self.check_host(host)
                if h == a.AGENT_HEADER:
                    self.agent.set_host(host)
                    self.fsm.announce()
                    return True

        l.warn("Instana Host Agent can't be found. Scheduling retry.")
        self.schedule_retry(self.lookup_agent_host, e, "agent_lookup")
        return False

    def get_default_gateway(self):
        l.debug("checking default gateway")

        try:
            proc = subprocess.Popen(
                "/sbin/ip route | awk '/default/' | cut -d ' ' -f 3 | tr -d '\n'", shell=True, stdout=subprocess.PIPE)

            addr = proc.stdout.read()
            return addr.decode("UTF-8")
        except Exception as e:
            l.error(e)

            return None

    def check_host(self, host):
        l.debug("checking host", host)

        (_, h) = self.agent.request_header(
            self.agent.make_host_url(host, "/"), "GET", "Server")

        return h

    def announce_sensor(self, e):
        l.debug("announcing sensor to the agent")
        p = psutil.Process(os.getpid())
        s = None

        d = Discovery(pid=p.pid,
                      name=p.cmdline()[0],
                      args=p.cmdline()[1:])

        # If we're on a system with a procfs
        if os.path.exists("/proc/"):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.agent.host, 42699))
            path = "/proc/%d/fd/%d" % (p.pid, s.fileno())
            d.fd = s.fileno()
            d.inode = os.readlink(path)

        (b, _) = self.agent.request_response(
            self.agent.make_url(a.AGENT_DISCOVERY_URL), "PUT", d)
        if b:
            self.agent.set_from(b)
            self.fsm.ready()
            l.warn("Host agent available. We're in business. Announced pid: %i (true pid: %i)" % (p.pid, self.agent.from_.pid))
            return True
        else:
            l.warn("Cannot announce sensor. Scheduling retry.")
            self.schedule_retry(self.announce_sensor, e, "announce")
        return False

    def schedule_retry(self, fun, e, name):
        l.debug("Scheduling: " + name)
        self.timer = t.Timer(self.RETRY_PERIOD, fun, [e])
        self.timer.daemon = True
        self.timer.name = name
        self.timer.start()
        l.debug('Threadlist: ', str(t.enumerate()))

    def test_agent(self, e):
        l.debug("testing communication with the agent")

        (b, _) = self.agent.head(self.agent.make_url(a.AGENT_DATA_URL))

        if not b:
            self.schedule_retry(self.test_agent, e, "agent test")
        else:
            self.fsm.test()
