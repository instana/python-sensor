# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
from .app import pyramid_server as server
from ..utils import launch_background_thread

app_thread = None

if 'CASSANDRA_TEST' not in os.environ:
    app_thread = launch_background_thread(server.serve_forever, "Pyramid")
