from __future__ import absolute_import
import os
import time
import threading
from .apps.flaskalino import app as flaskalino
from .apps.soapserver4132 import soapserver

os.environ["INSTANA_TEST"] = "true"


# Background Flask application
#
# Spawn our background Flask app that the tests will throw
# requests at.  Don't continue until the test app is fully
# up and running.
timer = threading.Thread(target=flaskalino.run)
timer.daemon = True
timer.name = "Background Flask app"
print("Starting background Flask app")
timer.start()


# Background Soap Server
#
# Spawn our background Flask app that the tests will throw
# requests at.  Don't continue until the test app is fully
# up and running.
timer = threading.Thread(target=soapserver.serve_forever)
timer.daemon = True
timer.name = "Background Soap server"
print("Starting background Soap server")
timer.start()


time.sleep(1)
