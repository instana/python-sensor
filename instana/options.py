import logging
import os
import sys


class Options(object):
    service = ''
    agent_host = ''
    agent_port = 0
    service_name = 'myservice'
    log_level = logging.WARN

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

        if "INSTANA_SERVICE_NAME" in os.environ:
            self.service_name = os.environ["INSTANA_SERVICE_NAME"]
        elif "FLASK_APP" in os.environ:
            self.service_name = os.environ["FLASK_APP"]
        elif "DJANGO_SETTINGS_MODULE" in os.environ:
            self.service_name = os.environ["DJANGO_SETTINGS_MODULE"].split('.')[0]
        elif hasattr(sys, '__interactivehook__') or hasattr(sys, 'ps1'):
            self.service_name = "Interactive Console"
        else:
            self.service_name = os.path.basename(sys.argv[0])


        self.__dict__.update(kwds)
