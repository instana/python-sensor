import grpc
import time
import tests.apps.grpc_server.stan_pb2 as stan_pb2
import tests.apps.grpc_server.stan_pb2_grpc as stan_pb2_grpc
from concurrent import futures


class StanServicer(stan_pb2_grpc.StanServicer):
    """
    gRPC server for Stan Service
    """
    def __init__(self, *args, **kwargs):
        self.server_port = 5030

    def AskQuestion(self, request, context):
        # get the string from the incoming request
        question = request.question

        response = """\
Invention, my dear friends, is 93% perspiration, 6% electricity, \
4% evaporation, and 2% butterscotch ripple. – Willy Wonka"""

        # # print the output here
        # print(response)54a

        result = {'answer': response, 'was_answered': True}

        return stan_pb2.QuestionResponse(**result)

    def start_server(self):
        """
        Function which actually starts the gRPC server, and preps
        it for serving incoming connections
        """
        # declare a server object with desired number
        # of thread pool workers.
        rpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

        # This line can be ignored
        stan_pb2_grpc.add_StanServicer_to_server(StanServicer(), rpc_server)

        # bind the server to the port defined above
        rpc_server.add_insecure_port('[::]:{}'.format(self.server_port))

        # start the server
        rpc_server.start()

        try:
            # need an infinite loop since the above
            # code is non blocking, and if I don't do this
            # the program will exit
            while True:
                time.sleep(60*60*60)
        except KeyboardInterrupt:
            rpc_server.stop(0)
            print('Stan as a Service RPC Server Stopped ...')

