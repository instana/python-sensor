import logging
import os


class Options(object):
    service = ''
    agent_host = ''
    agent_port = 0
    log_level = logging.WARN
    use_grpc_safe_http_headers = False

    def __init__(self, **kwds):
        """ Initialize Options
        Respect any environment variables that may be set.
        """
        if "INSTANA_DEV" in os.environ:
            self.log_level = logging.DEBUG

        if "INSTANA_AGENT_IP" in os.environ:
            # Deprecated: INSTANA_AGENT_IP environment variable
            # To be removed in a future version
            self.agent_host = os.environ["INSTANA_AGENT_IP"]

        if "INSTANA_AGENT_HOST" in os.environ:
            self.agent_host = os.environ["INSTANA_AGENT_HOST"]

        if "INSTANA_AGENT_PORT" in os.environ:
            self.agent_port = os.environ["INSTANA_AGENT_PORT"]

        if "USE_GRPC_SAFE_HTTP_HEADERS" in os.environ:
            self.use_grpc_safe_http_headers = os.environ["USE_GRPC_SAFE_HTTP_HEADERS"] == "true"

        self.__dict__.update(kwds)
