# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

import time
import xmlrpc.client

import opentracing  # type: ignore

while True:
    time.sleep(2)
    with opentracing.tracer.start_active_span("RPCJobRunner") as rscope:
        rscope.span.set_tag("span.kind", "entry")
        rscope.span.set_tag("http.url", "http://jobkicker.instana.com/runrpcjob")
        rscope.span.set_tag("http.method", "GET")
        rscope.span.set_tag("http.params", "secret=iloveyou")

        with opentracing.tracer.start_active_span("RPCClient") as scope:
            scope.span.set_tag("span.kind", "exit")
            scope.span.set_tag("rpc.host", "rpc-api.instana.com:8261")
            scope.span.set_tag("rpc.call", "dance")

            carrier = {}
            opentracing.tracer.inject(
                scope.span.context, opentracing.Format.HTTP_HEADERS, carrier
            )

            with xmlrpc.client.ServerProxy("http://localhost:8261/") as proxy:
                result = proxy.dance("NOW!", carrier)
                scope.span.set_tag("result", result)

        rscope.span.set_tag("http.status_code", 200)
