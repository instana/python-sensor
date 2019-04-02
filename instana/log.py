import logging as log
import os

logger = log.getLogger('instana')


def init(level):
    ch = log.StreamHandler()
    f = log.Formatter('%(asctime)s: %(process)d %(levelname)s %(name)s: %(message)s')
    ch.setFormatter(f)
    logger.addHandler(ch)
    if "INSTANA_DEV" in os.environ:
        logger.setLevel(log.DEBUG)
    else:
        logger.setLevel(level)


def debug(s, *args):
    logger.debug("%s %s", s, ' '.join(args))


def info(s, *args):
    logger.info("%s %s", s, ' '.join(args))


def warn(s, *args):
    logger.warn("%s %s", s, ' '.join(args))


def error(s, *args):
    logger.error("%s %s", s, ' '.join(args))
