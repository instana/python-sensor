import logging
import os


class StandardOptions(object):
    service = None
    service_name = None
    agent_host = None
    agent_port = None
    log_level = logging.WARN
    debug = None

    AGENT_DEFAULT_HOST = "localhost"
    AGENT_DEFAULT_PORT = 42699

    def __init__(self, **kwds):
        if "INSTANA_DEBUG" in os.environ:
            self.log_level = logging.DEBUG
            self.debug = True

        self.service_name = os.environ.get("INSTANA_SERVICE_NAME", None)
        self.agent_host = os.environ.get("INSTANA_AGENT_HOST", self.AGENT_DEFAULT_HOST)
        self.agent_port = os.environ.get("INSTANA_AGENT_PORT", self.AGENT_DEFAULT_PORT)

        if type(self.agent_port) is str:
            self.agent_port = int(self.agent_port)

        self.debug = os.environ.get("INSTANA_DEBUG", False)
        self.__dict__.update(kwds)


class AWSLambdaOptions:
    endpoint_url = None
    agent_key = None
    extra_http_headers = None
    timeout = None
    log_level = logging.WARN
    debug = None

    def __init__(self, **kwds):
        if "INSTANA_DEBUG" in os.environ:
            self.log_level = logging.DEBUG
            self.debug = True

        self.endpoint_url = os.environ.get("INSTANA_ENDPOINT_URL", None)

        # Remove any trailing slash (if any)
        if self.endpoint_url is not None and self.endpoint_url[-1] == "/":
            self.endpoint_url = self.endpoint_url[:-1]

        self.agent_key = os.environ.get("INSTANA_AGENT_KEY", None)

        self.extra_http_headers = os.environ.get("INSTANA_EXTRA_HTTP_HEADERS", None)
        self.timeout = os.environ.get("INSTANA_TIMEOUT", 0.5)
        self.log_level = os.environ.get("INSTANA_LOG_LEVEL", None)

        self.__dict__.update(kwds)
