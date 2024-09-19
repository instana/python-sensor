# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017

import os

if os.environ.get('GEVENT_STARLETTE_TEST'):
    from gevent import monkey
    monkey.patch_all()

