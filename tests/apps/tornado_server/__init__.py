# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import sys
from ...helpers import testenv
from ..utils import launch_background_thread

app_thread = None

if app_thread is None and sys.version_info >= (3, 5, 3) and 'GEVENT_TEST' not in os.environ and 'CASSANDRA_TEST' not in os.environ:
    testenv["tornado_port"] = 10813
    testenv["tornado_server"] = ("http://127.0.0.1:" + str(testenv["tornado_port"]))

    # Background Tornado application
    from .app import run_server

    app_thread = launch_background_thread(run_server, "Tornado")

