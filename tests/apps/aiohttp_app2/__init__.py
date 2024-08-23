# (c) Copyright IBM Corp. 2024

import os
import sys
from tests.apps.aiohttp_app2.app import aiohttp_server as server
from tests.apps.utils import launch_background_thread

APP_THREAD = None

if not any((os.environ.get('GEVENT_STARLETTE_TEST'),
            os.environ.get('CASSANDRA_TEST'),
            sys.version_info < (3, 5, 3))):
    APP_THREAD = launch_background_thread(server, "AIOHTTP")
