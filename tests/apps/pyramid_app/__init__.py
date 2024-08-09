# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os

from ..utils import launch_background_thread
from .app import pyramid_server as server

app_thread = None

if not os.environ.get("CASSANDRA_TEST"):
    app_thread = launch_background_thread(server.serve_forever, "Pyramid")
