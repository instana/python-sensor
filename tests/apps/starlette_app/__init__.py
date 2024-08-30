# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import uvicorn

from tests.helpers import testenv

testenv["starlette_host"] = "127.0.0.1"
testenv["starlette_port"] = 10817
testenv["starlette_server"] = (
    "http://" + testenv["starlette_host"] + ":" + str(testenv["starlette_port"])
)


def launch_starlette():
    from instana.singletons import agent

    from .app import starlette_server

    # Hack together a manual custom headers list; We'll use this in tests
    agent.options.extra_http_headers = [
        "X-Capture-This",
        "X-Capture-That",
    ]

    uvicorn.run(
        starlette_server,
        host=testenv["starlette_host"],
        port=testenv["starlette_port"],
        log_level="critical",
    )
