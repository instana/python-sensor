# encoding=utf-8

# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016

import os
import sys
import time

import opentracing as ot
import opentracing.ext.tags as ext

os.environ["INSTANA_SERVICE_NAME"] = "🦄 Stan ❤️s Python 🦄"


def main(argv):
    while True:
        time.sleep(2)
        simple()
    time.sleep(200)


def simple():
    with ot.tracer.start_active_span("asteroid") as pscope:
        pscope.span.set_tag(ext.COMPONENT, "Python simple example app")
        pscope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
        pscope.span.set_tag(ext.PEER_HOSTNAME, "localhost")
        pscope.span.set_tag(ext.HTTP_URL, "/python/simple/one")
        pscope.span.set_tag(ext.HTTP_METHOD, "GET")
        pscope.span.set_tag(ext.HTTP_STATUS_CODE, 200)
        pscope.span.set_tag("Pete's RequestId", "0xdeadbeef")
        pscope.span.set_tag("X-Peter-Header", "👀")
        pscope.span.set_tag("X-Job-Id", "1947282")
        time.sleep(0.2)

        with ot.tracer.start_active_span("spacedust", child_of=pscope.span) as cscope:
            cscope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_CLIENT)
            cscope.span.set_tag(ext.PEER_HOSTNAME, "localhost")
            cscope.span.set_tag(ext.HTTP_URL, "/python/simple/two")
            cscope.span.set_tag(ext.HTTP_METHOD, "POST")
            cscope.span.set_tag(ext.HTTP_STATUS_CODE, 204)
            cscope.span.set_baggage_item("someBaggage", "someValue")
            time.sleep(0.1)


if __name__ == "__main__":
    main(sys.argv)
