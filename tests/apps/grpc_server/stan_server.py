import os
import sys
import grpc
import time
import tests.apps.grpc_server.stan_pb2 as stan_pb2
import tests.apps.grpc_server.stan_pb2_grpc as stan_pb2_grpc
from concurrent import futures

try:
    from ...helpers import testenv
except ValueError:
    # We must be running from the command line...
    testenv = {}

testenv["grpc_port"] = 10814
testenv["grpc_host"] = "127.0.0.1"
testenv["grpc_server"] = testenv["grpc_host"] + ":" + str(testenv["grpc_port"])


class StanServicer(stan_pb2_grpc.StanServicer):
    """
    gRPC server for Stan Service
    """
    def __init__(self, *args, **kwargs):
        self.server_port = testenv['grpc_port']

    def OneQuestionOneResponse(self, request, context):
        # print("😇:I was asked: %s" % request.question)
        response = """\
Invention, my dear friends, is 93% perspiration, 6% electricity, \
4% evaporation, and 2% butterscotch ripple. – Willy Wonka"""
        result = {'answer': response, 'was_answered': True}
        return stan_pb2.QuestionResponse(**result)

    def ManyQuestionsOneResponse(self, request_iterator, context):
        for request in request_iterator:
            # print("😇:I was asked: %s" % request.question)
            pass

        result = {'answer': 'Ok', 'was_answered': True}
        return stan_pb2.QuestionResponse(**result)

    def OneQuestionManyResponses(self, request, context):
        # print("😇:I was asked: %s" % request.question)
        for count in range(6):
            result = {'answer': 'Ok', 'was_answered': True}
            yield stan_pb2.QuestionResponse(**result)

    def ManyQuestionsManyReponses(self, request_iterator, context):
        for request in request_iterator:
            # print("😇:I was asked: %s" % request.question)
            result = {'answer': 'Ok', 'was_answered': True}
            yield stan_pb2.QuestionResponse(**result)

    def OneQuestionOneErrorResponse(self, request, context):
            # print("😇:I was asked: %s" % request.question)
            raise Exception('Simulated error')
            result = {'answer': "ThisError", 'was_answered': True}
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


if __name__ == "__main__":
    print ("Booting foreground GRPC application...")
    # os.environ["INSTANA_TEST"] = "true"

    if sys.version_info >= (3, 5, 3):
        StanServicer().start_server()
    else:
        print("Python v3.5.3 or higher only")
