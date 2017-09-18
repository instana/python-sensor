import json
import instana.log as l
import instana.fsm as f
import instana.agent_const as a
import threading

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2


class From(object):
    pid = ""
    hostId = ""

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
    host = a.AGENT_DEFAULT_HOST
    port = a.AGENT_DEFAULT_PORT
    fsm = None
    from_ = None

    def __init__(self, sensor):
        l.debug("initializing agent")

        self.sensor = sensor
        self.fsm = f.Fsm(self)
        self.reset()

    def to_json(self, o):
        try:
            return json.dumps(o, default=lambda o: o.__dict__,
                              sort_keys=False, separators=(',', ':')).encode()
        except Exception as e:
            l.error("to_json: ", e, o)

    def can_send(self):
        return self.fsm.fsm.current == "good2go"

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
                    l.error("Request returned erroneous code",
                            response.getcode())
                    if self.can_send():
                        self.reset()
                else:
                    if body:
                        b = response.read()

                    if header:
                        h = response.info().get(header)

                    if method == "HEAD":
                        b = True
        except Exception as e:
            # No need to show the initial 404s or timeouts.  The agent
            # should handle those correctly.
            if not (type(e) is urllib2.HTTPError and e.code == 404):
                l.debug("%s: full_request_response: %s" % (threading.current_thread().name, str(e)))

        return (b, h)

    def make_url(self, prefix):
        return self.make_host_url(self.host, prefix)

    def make_host_url(self, host, prefix):
        port = self.sensor.options.agent_port
        if port == 0:
            port = a.AGENT_DEFAULT_PORT

        return self.make_full_url(host, port, prefix)

    def make_full_url(self, host, port, prefix):
        s = "http://%s:%s%s" % (host, str(port), prefix)
        if self.from_.pid != 0:
            s = "%s%s" % (s, self.from_.pid)

        return s

    def reset(self):
        self.from_ = From()
        self.fsm.reset()

    def set_host(self, host):
        self.host = host

    def set_port(self, port):
        self.port = port

    def set_from(self, from_):
        self.from_ = From(**json.loads(from_))
