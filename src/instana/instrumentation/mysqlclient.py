# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


from instana.log import logger
from instana.instrumentation.pep0249 import ConnectionFactory

try:
    import MySQLdb

    cf = ConnectionFactory(connect_func=MySQLdb.connect, module_name="mysql")

    setattr(MySQLdb, "connect", cf)
    if hasattr(MySQLdb, "Connect"):
        setattr(MySQLdb, "Connect", cf)

    logger.debug("Instrumenting mysqlclient")
except ImportError:
    pass
