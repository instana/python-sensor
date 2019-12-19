"""
The uwsgi and uwsgidecorators packages are added automatically to the Python environment
when running under uWSGI.  Here we attempt to detect the presence of these packages and
then use the appropriate hooks.
"""
from __future__ import absolute_import

from ..log import logger
from ..singletons import agent

try:
    import uwsgi
    import uwsgidecorators

    logger.warn("uWSGI options: %s", uwsgi.opt)

    if 'lazy-apps' not in uwsgi.opt or uwsgi.opt['lazy-apps'] is not True:
        @uwsgidecorators.postfork
        def uwsgi_handle_fork():
            """ This is our uWSGI hook to detect and act when worker processes are forked off. """
            logger.debug("Handling uWSGI fork...")
            agent.handle_fork()

        logger.debug("Applied uWSGI hooks")
    else:
        logger.debug("uWSGI lazy-apps enabled.  Not applying postfork hooks")
except ImportError as e:
    logger.debug('uwsgi hooks: decorators not available')
    pass
