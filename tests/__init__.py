from __future__ import absolute_import
import os
import time
import threading
import opentracing
import instana.tracer
from .apps.flaskalino import app as flaskalino
os.environ["INSTANA_TEST"] = "true"

opentracing.global_tracer = instana.tracer.InstanaTracer()

# Spawn our background Flask app that the tests will throw
# requests at.  Don't continue until the test app is fully
# up and running.
timer = threading.Thread(target=flaskalino.run)
timer.daemon = True
timer.name = "Test Flask app"
print("Starting background test app")
timer.start()
time.sleep(1)
