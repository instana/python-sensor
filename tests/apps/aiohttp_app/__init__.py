# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
from .app import aiohttp_server as server
from ..utils import launch_background_thread

APP_THREAD = None

if not any((os.environ.get("GEVENT_STARLETTE_TEST"), os.environ.get("CASSANDRA_TEST"))):
    APP_THREAD = launch_background_thread(server, "AIOHTTP")
