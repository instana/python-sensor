import logging


class Options(object):
    service = ''
    agent_host = ''
    agent_port = 0
    log_level = logging.WARN

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
