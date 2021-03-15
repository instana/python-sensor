# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

from __future__ import absolute_import

from ..log import logger
from .pep0249 import ConnectionFactory

try:
    import pymysql #

    cf = ConnectionFactory(connect_func=pymysql.connect, module_name='mysql')

    setattr(pymysql, 'connect', cf)
    if hasattr(pymysql, 'Connect'):
        setattr(pymysql, 'Connect', cf)

    logger.debug("Instrumenting pymysql")
except ImportError:
    pass
