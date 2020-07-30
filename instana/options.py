""" Options for the in-process Instana agent """
import os
import logging

from .log import logger
from .util import determine_service_name


class BaseOptions(object):
    def __init__(self, **kwds):
        self.debug = False
        self.log_level = logging.WARN
        self.service_name = determine_service_name()
        self.extra_http_headers = None

        if "INSTANA_DEBUG" in os.environ:
            self.log_level = logging.DEBUG
            self.debug = True
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            self.extra_http_headers = str(os.environ["INSTANA_EXTRA_HTTP_HEADERS"]).lower().split(';')

        # Defaults
        self.secrets_matcher = 'contains-ignore-case'
        self.secrets_list = ['key', 'pass', 'secret']

        # Env var format: <matcher>:<secret>[,<secret>]
        self.secrets = os.environ.get("INSTANA_SECRETS", None)

        if self.secrets is not None:
            parts = self.secrets.split(':')
            if len(parts) == 2:
                self.secrets_matcher = parts[0]
                self.secrets_list = parts[1].split(',')
            else:
                logger.warning("Couldn't parse INSTANA_SECRETS env var: %s", self.secrets)

        self.__dict__.update(kwds)


class StandardOptions(BaseOptions):
    """ Configurable option bits for this package """
    AGENT_DEFAULT_HOST = "localhost"
    AGENT_DEFAULT_PORT = 42699

    def __init__(self, **kwds):
        super(StandardOptions, self).__init__()

        self.agent_host = os.environ.get("INSTANA_AGENT_HOST", self.AGENT_DEFAULT_HOST)
        self.agent_port = os.environ.get("INSTANA_AGENT_PORT", self.AGENT_DEFAULT_PORT)

        if type(self.agent_port) is str:
            self.agent_port = int(self.agent_port)


class AWSLambdaOptions(BaseOptions):
    """ Configurable option bits for AWS Lambda """
    def __init__(self, **kwds):
        super(AWSLambdaOptions, self).__init__()

        self.endpoint_url = os.environ.get("INSTANA_ENDPOINT_URL", None)

        # Remove any trailing slash (if any)
        if self.endpoint_url is not None and self.endpoint_url[-1] == "/":
            self.endpoint_url = self.endpoint_url[:-1]

        self.agent_key = os.environ.get("INSTANA_AGENT_KEY", None)
        self.timeout = os.environ.get("INSTANA_TIMEOUT", 0.5)
        self.log_level = os.environ.get("INSTANA_LOG_LEVEL", None)


class AWSFargateOptions(BaseOptions):
    """ Configurable option bits for AWS Fargate """
    def __init__(self, **kwds):
        super(AWSFargateOptions, self).__init__()

        self.agent_key = os.environ.get("INSTANA_AGENT_KEY", None)
        self.endpoint_proxy = os.environ.get("INSTANA_ENDPOINT_PROXY", None)

        self.endpoint_url = os.environ.get("INSTANA_ENDPOINT_URL", None)
        # Remove any trailing slash (if any)
        if self.endpoint_url is not None and self.endpoint_url[-1] == "/":
            self.endpoint_url = self.endpoint_url[:-1]

        self.log_level = os.environ.get("INSTANA_LOG_LEVEL", None)
        self.tags = os.environ.get("INSTANA_TAGS", None)
        self.timeout = os.environ.get("INSTANA_TIMEOUT", 0.5)
        self.zone = os.environ.get("INSTANA_ZONE", None)

