# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


import uvicorn
from ...helpers import testenv
from instana.log import logger

testenv["sanic_port"] = 1337
testenv["sanic_server"] = ("http://127.0.0.1:" + str(testenv["sanic_port"]))


def launch_sanic():
    from .server import app
    from instana.singletons import agent

    # Hack together a manual custom headers list; We'll use this in tests
    agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

    uvicorn.run(app, host='127.0.0.1', port=testenv['sanic_port'], log_level="critical")
