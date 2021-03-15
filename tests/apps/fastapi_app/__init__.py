# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import uvicorn
from ...helpers import testenv
from instana.log import logger

testenv["fastapi_port"] = 10816
testenv["fastapi_server"] = ("http://127.0.0.1:" + str(testenv["fastapi_port"]))

def launch_fastapi():
    from .app import fastapi_server
    from instana.singletons import agent

    # Hack together a manual custom headers list; We'll use this in tests
    agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

    uvicorn.run(fastapi_server, host='127.0.0.1', port=testenv['fastapi_port'], log_level="critical")
