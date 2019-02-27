import grpc
import time
import hashlib
import tests.apps.grpc_server.stan_pb2 as stan_pb2
import tests.apps.grpc_server.stan_pb2_grpc as stan_pb2_grpc
from concurrent import futures

class StanServicer(stan_pb2_grpc.StanServicer):
    """
    gRPC server for Stan Service
    """
    def __init__(self, *args, **kwargs):
        self.server_port = 5003

    def SayHello(self, request, context):
        """
        Implementation of the rpc SayHello declared in the proto
        file above.
        """
        # get the string from the incoming request
        to_be_digested = request.SayHello

        # digest and get the string representation
        # from the digestor
        hasher = hashlib.sha256()
        hasher.update(to_be_digested.encode())
        response = hasher.hexdigest()

        # print the output here
        print(response)

        result = {'Digested': response, 'WasDigested': True}

        return stan_pb2.OutgoingMessage(**result)

    def start_server(self):
        """
        Function which actually starts the gRPC server, and preps
        it for serving incoming connections
        """
        # declare a server object with desired number
        # of thread pool workers.
        digestor_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

        # This line can be ignored
        stan_pb2_grpc.add_StanServicer_to_server(StanServicer(),digestor_server)

        # bind the server to the port defined above
        digestor_server.add_insecure_port('[::]:{}'.format(self.server_port))

        # start the server
        digestor_server.start()
        print ('Stan as a Service RPC Server running ...')

        try:
            # need an infinite loop since the above
            # code is non blocking, and if I don't do this
            # the program will exit
            while True:
                time.sleep(60*60*60)
        except KeyboardInterrupt:
            digestor_server.stop(0)
            print('Stan as a Service RPC Server Stopped ...')

