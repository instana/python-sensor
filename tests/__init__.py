from __future__ import absolute_import
import os

os.environ["INSTANA_TEST"] = "true"

if 'GEVENT_TEST' in os.environ:
    from gevent import monkey
    monkey.patch_all()

