import os
import uvicorn
from ...helpers import testenv
from .app import fastapi_server
from ..utils import launch_background_thread
from instana.log import logger

APP_THREAD = None

def launch_fastapi(mp_queue):
    from instana.singletons import agent
    agent.collector.span_queue = mp_queue
    logger.warning('Child PID: %s', os.getpid())
    logger.warning('Child mp_queue: %s', mp_queue)
    uvicorn.run(fastapi_server, host='127.0.0.1', port=testenv['fastapi_port'])
