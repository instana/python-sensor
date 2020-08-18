"""
Option classes for the in-process Instana agent

The description and hierarchy of the classes in this file are as follows:

BaseOptions - base class for all environments.  Holds settings common to all.
  - StandardOptions - The options class used when running directly on a host/node with an Instana agent
  - ServerlessOptions - Base class for serverless environments.  Holds settings common to all serverless environments.
    - AWSLambdaOptions - Options class for AWS Lambda.  Holds settings specific to AWS Lambda.
    - AWSFargateOptions - Options class for AWS Fargate.  Holds settings specific to AWS Fargate.
"""
import os
import logging

from .log import logger
from .util import determine_service_name


class BaseOptions(object):
    """ Base class for all option classes.  Holds items common to all """
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
    """ The options class used when running directly on a host/node with an Instana agent """
    AGENT_DEFAULT_HOST = "localhost"
    AGENT_DEFAULT_PORT = 42699

    def __init__(self, **kwds):
        super(StandardOptions, self).__init__()

        self.agent_host = os.environ.get("INSTANA_AGENT_HOST", self.AGENT_DEFAULT_HOST)
        self.agent_port = os.environ.get("INSTANA_AGENT_PORT", self.AGENT_DEFAULT_PORT)

        if not isinstance(self.agent_port, int):
            self.agent_port = int(self.agent_port)


class ServerlessOptions(BaseOptions):
    """ Base class for serverless environments.  Holds settings common to all serverless environments. """
    def __init__(self, **kwds):
        super(ServerlessOptions, self).__init__()

        self.agent_key = os.environ.get("INSTANA_AGENT_KEY", None)
        self.endpoint_url = os.environ.get("INSTANA_ENDPOINT_URL", None)

        # Remove any trailing slash (if any)
        if self.endpoint_url is not None and self.endpoint_url[-1] == "/":
            self.endpoint_url = self.endpoint_url[:-1]

        if 'INSTANA_DISABLE_CA_CHECK' in os.environ:
            self.ssl_verify = False
        else:
            self.ssl_verify = True

        proxy = os.environ.get("INSTANA_ENDPOINT_PROXY", None)
        if proxy is None:
            self.endpoint_proxy = {}
        else:
            self.endpoint_proxy = {'https': proxy}

        timeout_in_ms = os.environ.get("INSTANA_TIMEOUT", None)
        if timeout_in_ms is None:
            self.timeout = 0.8
        else:
            # Convert the value from milliseconds to seconds for the requests package
            try:
                self.timeout = int(timeout_in_ms) / 1000
            except ValueError:
                logger.warning("Likely invalid INSTANA_TIMEOUT=%s value.  Using default.", timeout_in_ms)
                logger.warning("INSTANA_TIMEOUT should specify timeout in milliseconds.  See "
                               "https://www.instana.com/docs/reference/environment_variables/#serverless-monitoring")
                self.timeout = 0.8

        value = os.environ.get("INSTANA_LOG_LEVEL", None)
        if value is not None:
            try:
                value = value.lower()
                if value == "debug":
                    self.log_level = logging.DEBUG
                elif value == "info":
                    self.log_level = logging.INFO
                elif value == "warn" or value == "warning":
                    self.log_level = logging.WARNING
                elif value == "error":
                    self.log_level = logging.ERROR
                else:
                    logger.warning("Unknown INSTANA_LOG_LEVEL specified: %s", value)
            except Exception:
                logger.debug("BaseAgent.update_log_level: ", exc_info=True)

class AWSLambdaOptions(ServerlessOptions):
    """ Options class for AWS Lambda.  Holds settings specific to AWS Lambda. """
    def __init__(self, **kwds):
        super(AWSLambdaOptions, self).__init__()


class AWSFargateOptions(ServerlessOptions):
    """ Options class for AWS Fargate.  Holds settings specific to AWS Fargate. """
    def __init__(self, **kwds):
        super(AWSFargateOptions, self).__init__()

        self.tags = None
        tag_list = os.environ.get("INSTANA_TAGS", None)
        if tag_list is not None:
            try:
                self.tags = dict()
                tags = tag_list.split(',')
                for tag_and_value in tags:
                    parts = tag_and_value.split('=')
                    length = len(parts)
                    if length == 1:
                        self.tags[parts[0]] = None
                    elif length == 2:
                        self.tags[parts[0]] = parts[1]
            except Exception:
                logger.debug("Error parsing INSTANA_TAGS env var: %s", tag_list)

        self.zone = os.environ.get("INSTANA_ZONE", None)
