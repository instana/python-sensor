# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


import uvicorn
from instana.log import logger  # noqa: F401

from ...helpers import testenv

testenv["sanic_port"] = 1337
testenv["sanic_server"] = "http://127.0.0.1:" + str(testenv["sanic_port"])


def launch_sanic():
    from instana.singletons import agent

    from .server import app

    # Hack together a manual custom headers list; We'll use this in tests
    agent.options.extra_http_headers = [
        "X-Capture-This",
        "X-Capture-That",
        "X-Capture-This-Too",
        "X-Capture-That-Too",
    ]

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=testenv["sanic_port"],
        log_level="critical",
    )
