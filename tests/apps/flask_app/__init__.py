import os
from .app import flask_server as server
from ..utils import launch_background_thread

app_thread = None

if 'CASSANDRA_TEST' not in os.environ and app_thread is None:
    app_thread = launch_background_thread(server.serve_forever, "Flask")
