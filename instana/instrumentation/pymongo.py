from __future__ import absolute_import

from ..log import logger

try:
    import pymongo
    from pymongo import monitoring

    class MongoCommandTracer(monitoring.CommandListener):

        def started(self, event):
            logger.debug("Command {0.command_name}({0.command}) with request id {0.request_id} started on server {0.connection_id}".format(event))

        def succeeded(self, event):
            logger.debug("Command {0.command_name} with request id {0.request_id} succeeded on server {0.connection_id}".format(event))

        def failed(self, event):
            logger.debug("Command {0.command_name} with request id {0.request_id} failed on server {0.connection_id}".format(event))

    monitoring.register(MongoCommandTracer())
    
    logger.debug("Instrumenting pymongo")
    
except ImportError:
    pass

