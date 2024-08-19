# (c) Copyright IBM Corp. 2024

import os
from tests.apps.bottle_app.app import bottle_server as server
from tests.apps.utils import launch_background_thread

app_thread = None

if not os.environ.get('CASSANDRA_TEST') and app_thread is None:
    app_thread = launch_background_thread(server.serve_forever, "Bottle")