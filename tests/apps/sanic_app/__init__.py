# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


import uvicorn

from tests.helpers import testenv

testenv["sanic_port"] = 1337
testenv["sanic_server"] = f"http://127.0.0.1:{testenv['sanic_port']}"


def launch_sanic():
    from .server import app
    from instana.singletons import agent

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
