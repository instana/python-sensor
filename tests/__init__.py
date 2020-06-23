from __future__ import absolute_import
import os
import sys

os.environ["INSTANA_TEST"] = "true"

if 'GEVENT_TEST' in os.environ:
    from gevent import monkey
    monkey.patch_all()

# Avoid loading the background test apps in the background
# Celery worker that is spawned with this test suite
if os.path.basename(sys.argv[0]) != 'celery':
    import tests.apps

