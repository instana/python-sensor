"""
The in-process Instana agent (for testing & the test suite) that manages
monitoring state and reporting that data.
"""
import os
from ..log import logger
from .host import HostAgent


class TestAgent(HostAgent):
    """
    Special Agent for the test suite.  This agent is based on the StandardAgent.  Overrides here are only for test
    purposes and mocking.
    """
    def get_from_structure(self):
        """
        Retrieves the From data that is reported alongside monitoring data.
        @return: dict()
        """
        return {'e': os.getpid(), 'h': 'fake'}

    def can_send(self):
        """
        Are we in a state where we can send data?
        @return: Boolean
        """
        return True

    def report_traces(self, spans):
        logger.warning("Tried to report_traces with a TestAgent!")
