import os
import sys
import time
import threading

if 'CASSANDRA_TEST' not in os.environ:
    from .flaskalino import flask_server
    from .app_pyramid import pyramid_server

    # Background applications
    servers = {
        'Flask': flask_server,
        'Pyramid': pyramid_server,
    }

    # Spawn background apps that the tests will throw
    # requests at.
    for (name, server) in servers.items():
        p = threading.Thread(target=server.serve_forever)
        p.daemon = True
        p.name = "Background %s app" % name
        print("Starting background %s app..." % name)
        p.start()

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

    if sys.version_info < (3, 7, 0):
        # Background Soap Server
        from .soapserver4132 import soapserver

        # Spawn our background Soap server that the tests will throw
        # requests at.
        soap = threading.Thread(target=soapserver.serve_forever)
        soap.daemon = True
        soap.name = "Background Soap server"
        print("Starting background Soap server...")
        soap.start()

    if sys.version_info >= (3, 5, 3):
        # Background aiohttp application
        from .app_aiohttp import run_server

        # Spawn our background aiohttp app that the tests will throw
        # requests at.
        aio_server = threading.Thread(target=run_server)
        aio_server.daemon = True
        aio_server.name = "Background aiohttp server"
        print("Starting background aiohttp server...")
        aio_server.start()

    if sys.version_info >= (3, 5, 3):
        # Background Tornado application
        from .tornado import run_server

        # Spawn our background Tornado app that the tests will throw
        # requests at.
        tornado_server = threading.Thread(target=run_server)
        tornado_server.daemon = True
        tornado_server.name = "Background Tornado server"
        print("Starting background Tornado server...")
        tornado_server.start()

time.sleep(1)
