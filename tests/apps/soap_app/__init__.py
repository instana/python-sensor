# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import sys
from .app import soapserver as server
from ..utils import launch_background_thread

app_thread = None

if sys.version_info < (3, 7, 0) and app_thread is None:
    app_thread = launch_background_thread(server.serve_forever, "SoapServer")

