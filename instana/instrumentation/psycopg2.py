from __future__ import absolute_import

from ..log import logger
from .pep0249 import ConnectionFactory

try:
    import psycopg2

    cf = ConnectionFactory(connect_func=psycopg2.connect, module_name='postgres')

    setattr(psycopg2, 'connect', cf)
    if hasattr(psycopg2, 'Connect'):
        setattr(psycopg2, 'Connect', cf)

    logger.debug("Instrumenting psycopg2")
except ImportError:
    pass
