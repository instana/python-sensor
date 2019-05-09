from __future__ import absolute_import
import os
import sys
import time
import threading

from .apps.flaskalino import flask_server

os.environ["INSTANA_TEST"] = "true"


# Background Flask application
#
# Spawn our background Flask app that the tests will throw
# requests at.
flask = threading.Thread(target=flask_server.serve_forever)
flask.daemon = True
flask.name = "Background Flask app"
print("Starting background Flask app...")
flask.start()


if sys.version_info < (3, 7, 0):
    # Background Soap Server
    from .apps.soapserver4132 import soapserver

    # Spawn our background Soap server that the tests will throw
    # requests at.
    soap = threading.Thread(target=soapserver.serve_forever)
    soap.daemon = True
    soap.name = "Background Soap server"
    print("Starting background Soap server...")
    soap.start()


if sys.version_info >= (3, 5, 3):
    # Background aiohttp application
    from .apps.app_aiohttp import run_server

    # Spawn our background aiohttp app that the tests will throw
    # requests at.
    aio_server = threading.Thread(target=run_server)
    aio_server.daemon = True
    aio_server.name = "Background aiohttp server"
    print("Starting background aiohttp server...")
    aio_server.start()


if sys.version_info >= (3, 5, 3):
    # Background Tornado application
    from .apps.tornado import run_server

    # Spawn our background Tornado app that the tests will throw
    # requests at.
    tornado_server = threading.Thread(target=run_server)
    tornado_server.daemon = True
    tornado_server.name = "Background Tornado server"
    print("Starting background Tornado server...")
    tornado_server.start()

time.sleep(1)
