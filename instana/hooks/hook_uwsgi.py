from __future__ import absolute_import

from ..log import logger
from ..singletons import agent

try:
    import uwsgidecorators

    @uwsgidecorators.postfork
    def uwsgi_handle_fork():
        """ This is our uWSGI hook to detect and act when worker processes are forked off. """
        logger.debug("Handling uWSGI fork...")
        agent.handle_fork()

    logger.debug("Applied uWSGI hooks")
except ImportError as e:
    logger.debug('uwsgi hooks: decorators not available')
    pass