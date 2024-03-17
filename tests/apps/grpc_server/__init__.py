# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

import os
import sys
import time
import threading

if not any((os.environ.get('GEVENT_STARLETTE_TEST'),
            os.environ.get('CASSANDRA_TEST'),
            sys.version_info < (3, 5, 3))):
    # Background RPC application
    #
    # Spawn the background RPC app that the tests will throw
    # requests at.
    import tests.apps.grpc_server
    from .stan_server import StanServicer
    stan_servicer = StanServicer()
    rpc_server_thread = threading.Thread(target=stan_servicer.start_server)
    rpc_server_thread.daemon = True
    rpc_server_thread.name = "Background RPC app"
    print("Starting background RPC app...")
    rpc_server_thread.start()
    time.sleep(1)
