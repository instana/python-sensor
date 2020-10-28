import os
import uvicorn
from ...helpers import testenv
from ..utils import launch_background_thread
from instana.log import logger

testenv["starlette_port"] = 10817
testenv["starlette_server"] = ("http://127.0.0.1:" + str(testenv["starlette_port"]))

def launch_starlette(mp_queue):
    from .app import starlette_server
    from instana.singletons import agent

    # Use the multiprocess queue
    agent.collector.span_queue = mp_queue
    # Hack together a manual custom headers list; We'll use this in tests
    agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

    logger.warning('Child PID: %s', os.getpid())
    logger.warning('Child mp_queue: %s', mp_queue)
    uvicorn.run(starlette_server, host='127.0.0.1', port=testenv['starlette_port'])
