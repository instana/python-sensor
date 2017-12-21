# encoding=utf-8
import sys
from instana import options as o
import logging
import opentracing as ot
from instana import tracer
import time
import opentracing.ext.tags as ext

SERVICE = "🦄 Stan ❤️s Python 🦄"


def main(argv):
    tracer.init(o.Options(service=SERVICE,
                          log_level=logging.DEBUG))

    while (True):
        time.sleep(2)
        simple()
    time.sleep(200)


def simple():
    parent_span = ot.tracer.start_span(operation_name="asteroid")
    parent_span.set_tag(ext.COMPONENT, "Python simple example app")
    parent_span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
    parent_span.set_tag(ext.PEER_HOSTNAME, "localhost")
    parent_span.set_tag(ext.HTTP_URL, "/python/simple/one")
    parent_span.set_tag(ext.HTTP_METHOD, "GET")
    parent_span.set_tag(ext.HTTP_STATUS_CODE, 200)
    parent_span.log_kv({"foo": "bar"})

    child_span = ot.tracer.start_span(operation_name="spacedust", child_of=parent_span)
    child_span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_CLIENT)
    child_span.set_tag(ext.PEER_HOSTNAME, "localhost")
    child_span.set_tag(ext.HTTP_URL, "/python/simple/two")
    child_span.set_tag(ext.HTTP_METHOD, "POST")
    child_span.set_tag(ext.HTTP_STATUS_CODE, 204)
    child_span.set_baggage_item("someBaggage", "someValue")

    time.sleep(.1)
    child_span.finish()

    time.sleep(.2)
    parent_span.finish()


if __name__ == "__main__":
    main(sys.argv)
