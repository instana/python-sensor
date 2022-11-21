# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017

from __future__ import absolute_import
import os

os.environ["INSTANA_TEST"] = "true"

if os.environ.get('GEVENT_TEST'):
    from gevent import monkey
    monkey.patch_all()

