# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

from __future__ import absolute_import

from ..log import logger
from .pep0249 import ConnectionFactory

try:
    import MySQLdb

    cf = ConnectionFactory(connect_func=MySQLdb.connect, module_name='mysql')

    setattr(MySQLdb, 'connect', cf)
    if hasattr(MySQLdb, 'Connect'):
        setattr(MySQLdb, 'Connect', cf)

    logger.debug("Instrumenting mysql-python")
except ImportError:
    pass
