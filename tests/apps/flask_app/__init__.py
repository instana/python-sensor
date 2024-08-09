# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os

from ..utils import launch_background_thread
from .app import flask_server as server

app_thread = None

if not os.environ.get("CASSANDRA_TEST") and app_thread is None:
    app_thread = launch_background_thread(server.serve_forever, "Flask")
