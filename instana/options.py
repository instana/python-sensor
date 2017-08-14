import logging
import os


class Options(object):
    service = ''
    agent_host = ''
    agent_port = 0
    log_level = logging.WARN

    def __init__(self, **kwds):
        if "INSTANA_DEV" in os.environ:
            self.log_level = logging.DEBUG

        self.__dict__.update(kwds)
