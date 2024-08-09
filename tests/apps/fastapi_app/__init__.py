# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import uvicorn
from instana.log import logger  # noqa: F401

from ...helpers import testenv

testenv["fastapi_port"] = 10816
testenv["fastapi_server"] = "http://127.0.0.1:" + str(testenv["fastapi_port"])


def launch_fastapi():
    from instana.singletons import agent

    from .app import fastapi_server

    # Hack together a manual custom headers list; We'll use this in tests
    agent.options.extra_http_headers = [
        "X-Capture-This",
        "X-Capture-That",
        "X-Capture-This-Too",
        "X-Capture-That-Too",
    ]

    uvicorn.run(
        fastapi_server,
        host="127.0.0.1",
        port=testenv["fastapi_port"],
        log_level="critical",
    )
