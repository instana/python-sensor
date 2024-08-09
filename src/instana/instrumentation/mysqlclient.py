# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


from ..log import logger
from .pep0249 import ConnectionFactory

try:
    import MySQLdb

    cf = ConnectionFactory(connect_func=MySQLdb.connect, module_name="mysql")

    MySQLdb.connect = cf
    if hasattr(MySQLdb, "Connect"):
        MySQLdb.Connect = cf

    logger.debug("Instrumenting mysqlclient")
except ImportError:
    pass
