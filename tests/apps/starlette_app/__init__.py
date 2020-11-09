import uvicorn
from ...helpers import testenv
from instana.log import logger

testenv["starlette_port"] = 10817
testenv["starlette_server"] = ("http://127.0.0.1:" + str(testenv["starlette_port"]))

def launch_starlette():
    from .app import starlette_server
    from instana.singletons import agent

    # Hack together a manual custom headers list; We'll use this in tests
    agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

    uvicorn.run(starlette_server, host='127.0.0.1', port=testenv['starlette_port'], log_level="critical")
