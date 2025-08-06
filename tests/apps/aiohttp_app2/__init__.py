# (c) Copyright IBM Corp. 2024

import os
from tests.apps.aiohttp_app2.app import aiohttp_server as server
from tests.apps.utils import launch_background_thread

APP_THREAD = None

if not any((os.environ.get("GEVENT_STARLETTE_TEST"), os.environ.get("CASSANDRA_TEST"))):
    APP_THREAD = launch_background_thread(server, "AIOHTTP")
