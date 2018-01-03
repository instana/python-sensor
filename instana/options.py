import logging
import os


class Options(object):
    service = ''
    agent_host = ''
    agent_port = 0
    log_level = logging.WARN

    def __init__(self, **kwds):
        """ Initialize Options
        Respect any environment variables that may be set.
        """
        if "INSTANA_DEV" in os.environ:
            self.log_level = logging.DEBUG

        if "INSTANA_AGENT_IP" in os.environ:
            self.agent_host = os.environ["INSTANA_AGENT_IP"]

        if "INSTANA_AGENT_PORT" in os.environ:
            self.agent_port = os.environ["INSTANA_AGENT_PORT"]

        self.__dict__.update(kwds)
