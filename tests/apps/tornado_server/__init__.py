# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os

from ...helpers import testenv
from ..utils import launch_background_thread

app_thread = None

if not any((app_thread, os.environ.get('GEVENT_STARLETTE_TEST'), os.environ.get('CASSANDRA_TEST'))):
    testenv["tornado_port"] = 10813
    testenv["tornado_server"] = ("http://127.0.0.1:" + str(testenv["tornado_port"]))

    # Background Tornado application
    from .app import run_server

    app_thread = launch_background_thread(run_server, "Tornado")

