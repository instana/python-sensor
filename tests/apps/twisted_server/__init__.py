# (c) Copyright IBM Corp. 2026

import os
import socket

from tests.apps.utils import launch_background_thread
from tests.helpers import testenv

app_thread = None


def _get_free_port() -> int:
    """Ask the OS for a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


if not any((
    app_thread,
    os.environ.get("GEVENT_TEST"),
    os.environ.get("CASSANDRA_TEST"),
)):
    testenv["twisted_port"] = _get_free_port()
    testenv["twisted_server"] = "http://127.0.0.1:" + str(testenv["twisted_port"])

    # Background Twisted application
    from .app import run_server

    app_thread = launch_background_thread(run_server, "Twisted")
