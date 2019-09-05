import logging
import os
import sys

logger = None


def get_standard_logger():
    """
    Retrieves and configures a standard logger for the Instana package

    :return: Logger
    """
    standard_logger = logging.getLogger("instana")

    ch = logging.StreamHandler()
    f = logging.Formatter('%(asctime)s: %(process)d %(levelname)s %(name)s: %(message)s')
    ch.setFormatter(f)
    standard_logger.addHandler(ch)
    if "INSTANA_DEBUG" in os.environ:
        standard_logger.setLevel(logging.DEBUG)
    else:
        standard_logger.setLevel(logging.WARN)

    return standard_logger


def running_in_gunicorn():
    """
    Determines if we are running inside of a gunicorn process and that the gunicorn logging package
    is available.

    :return:  Boolean
    """
    process_check = False
    package_check = False

    if hasattr(sys, 'argv'):
        for arg in sys.argv:
            if arg.find('gunicorn') >= 0:
                process_check = True
    else:
        # We have no command line so rely on the gunicorn package presence entirely
        process_check = True

    try:
        from gunicorn import glogging
    except ImportError:
        pass
    else:
        package_check = True

    return process_check and package_check


if running_in_gunicorn():
    logger = logging.getLogger("gunicorn.error")
else:
    logger = get_standard_logger()
