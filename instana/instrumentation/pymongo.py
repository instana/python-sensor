from __future__ import absolute_import

from ..log import logger

try:
    import pymongo
    from pymongo import monitoring

    class MongoCommand:
        def __init__(self, name, query):
            self.name = name
            self.query = query

    class MongoCommandTracer(monitoring.CommandListener):
        def __init__(self):
            self.__active_commands = {}

        def started(self, event):
            self.__active_commands[event.request_id] = MongoCommand(event.command_name,  event.command)
            logger.debug("Command {0.command_name}({0.command}) with request id {0.request_id} started on server {0.connection_id}".format(event))

        def succeeded(self, event):
            try:
                logger.debug("Command {0.command_name}({1.query}) with request id {0.request_id} succeeded on server {0.connection_id}".format(event, self.__active_commands[event.request_id]))
                del self.__active_commands[event.request_id]
            except KeyError:
                logger.warn("Request {} was not found in the requests list".format(event.request_id))

        def failed(self, event):
            try:
                logger.debug("Command {0.command_name}({1.query}) with request id {0.request_id} failed on server {0.connection_id}".format(event, self.__active_commands[event.request_id]))
                del self.__active_commands[event.request_id]
            except KeyError:
                logger.warn("Request {} was not found in the requests list".format(event.request_id))
        
    monitoring.register(MongoCommandTracer())
    
    logger.debug("Instrumenting pymongo")
    
except ImportError:
    pass

