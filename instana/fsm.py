import subprocess
import os
import sys
import threading as t
import fysom as f
import instana.log as l

class Discovery(object):
    pid = 0
    name = None
    args = None
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class Fsm(object):
    E_START     = "start"
    E_LOOKUP   = "lookup"
    E_ANNOUNCE = "announce"
    E_TEST     = "test"

    RETRY_PERIOD = 5#30

    agent = None
    fsm = None

    def __init__(self, agent):
        l.debug("initializing fsm")

        self.agent = agent
        self.fsm = f.Fysom({
    		"initial": "none",
    		"events": [
    			{"name": self.E_START, "src": ["none", "unannounced", "announced", "ready"], "dst": "init"},
    			{"name": self.E_LOOKUP, "src": "init", "dst": "unannounced"},
    			{"name": self.E_ANNOUNCE, "src": "unannounced", "dst": "announced"},
    			{"name": self.E_TEST, "src": "announced", "dst": "ready"}],
    		"callbacks": {
    			"onstart": self.lookup_agent_host,
    			"onenterunannounced": self.announce_sensor,
    			"onenterannounced": self.test_agent}})

    def reset(self):
        self.fsm.start()

    def lookup_agent_host(self, e):
        if self.agent.sensor.options.agent_host != "":
            host = self.agent.sensor.options.agent_host
        else:
            host = self.agent.AGENT_DEFAULT_HOST

        h = self.check_host(host)
        if h == self.agent.AGENT_HEADER:
            self.agent.set_host(host)
            self.fsm.lookup()
        else:
            self.check_host(self.get_default_gateway())
            if h == self.agent.AGENT_HEADER:
                self.agent.set_host(host)
                self.fsm.lookup()

    def get_default_gateway(self):
        l.debug("checking default gateway")
        proc = subprocess.Popen("/sbin/ip route | awk '/default/ { print $3 }'", stdout=subprocess.PIPE)

        return proc.stdout.read()

    def check_host(self, host):
        l.debug("checking host", host)

        (b, h) = self.agent.request_header(self.agent.make_host_url(host, "/"), "GET", "Server")

        return h

    def announce_sensor(self, e):
        l.debug("announcing sensor to the agent")

        d = Discovery(pid=os.getpid(),
                      name=sys.executable,
                      args=sys.argv[0:])

        (b, h) = self.agent.request_response(self.agent.make_url(self.agent.AGENT_DISCOVERY_URL), "PUT", d)
        if not b:
            l.error("Cannot announce sensor. Scheduling retry.")
            self.schedule_retry(self.announce_sensor, e)
        else:
            self.agent.set_from(b)
            self.fsm.announce()

    def schedule_retry(self, f, e):
        t.Timer(self.RETRY_PERIOD, f, [e]).start()

    def test_agent(self, e):
        l.debug("testing communication with the agent")

        (b, h) = self.agent.head(self.agent.make_url(self.agent.AGENT_DATA_URL))

        if not b:
            self.schedule_retry(self.test_agent, e)
        else:
            self.fsm.test()
