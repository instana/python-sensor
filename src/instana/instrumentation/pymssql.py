# (c) Copyright IBM Corp. 2026

from instana.log import logger
from instana.instrumentation.pep0249 import ConnectionFactory

try:
    import pymssql

    cf = ConnectionFactory(connect_func=pymssql.connect, module_name="mssql")

    setattr(pymssql, "connect", cf)
    if hasattr(pymssql, "Connect"):
        setattr(pymssql, "Connect", cf)

    logger.debug("Instrumenting pymssql")
except ImportError:
    pass
