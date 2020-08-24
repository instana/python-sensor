import os
import sys
import time
import threading

if 'GEVENT_TEST' not in os.environ and 'CASSANDRA_TEST' not in os.environ:
    if sys.version_info >= (3, 5, 3):
        # Background RPC application
        #
        # Spawn the background RPC app that the tests will throw
        # requests at.
        import tests.apps.grpc_server
        from .grpc_server.stan_server import StanServicer
        stan_servicer = StanServicer()
        rpc_server_thread = threading.Thread(target=stan_servicer.start_server)
        rpc_server_thread.daemon = True
        rpc_server_thread.name = "Background RPC app"
        print("Starting background RPC app...")
        rpc_server_thread.start()

time.sleep(1)
