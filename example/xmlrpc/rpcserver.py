from xmlrpc.server import SimpleXMLRPCServer

import opentracing


def dance(payload, carrier):
    ctx = opentracing.tracer.extract(opentracing.Format.HTTP_HEADERS, carrier)

    with opentracing.tracer.start_active_span('RPCServer', child_of=ctx) as scope:
        scope.span.set_tag("span.kind", "entry")
        scope.span.set_tag("rpc.call", "dance")
        scope.span.set_tag("rpc.host", "rpc-api.instana.com:8261")

        return "♪┏(°.°)┛┗(°.°)┓%s┗(°.°)┛┏(°.°)┓ ♪" % str(payload)


server = SimpleXMLRPCServer(("localhost", 8261))
print("Listening on port 8261...")
server.register_function(dance, "dance")
server.serve_forever()