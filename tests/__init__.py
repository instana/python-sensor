from __future__ import absolute_import
import os
import time
import threading

from .apps.flaskalino import flask_server
from .apps.soapserver4132 import soapserver

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


# Background Soap Server
#
# Spawn our background Soap server that the tests will throw
# requests at.
soap = threading.Thread(target=soapserver.serve_forever)
soap.daemon = True
soap.name = "Background Soap server"
print("Starting background Soap server...")
soap.start()


time.sleep(1)
