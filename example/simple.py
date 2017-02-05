import sys
import instana.options as o
import logging
import opentracing as ot
import instana.tracer
import time
import opentracing.ext.tags as ext

SERVICE = "python-simple"

def main(argv):
    instana.tracer.init(o.Options(service=SERVICE,
                                  log_level=logging.DEBUG))

    while (True):
        simple()

def simple():
    parent_span = ot.tracer.start_span(operation_name="parent")
    parent_span.set_tag(ext.COMPONENT, SERVICE)
    parent_span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
    parent_span.set_tag(ext.PEER_HOSTNAME, "localhost")
    parent_span.set_tag(ext.HTTP_URL, "/python/simple/one")
    parent_span.set_tag(ext.HTTP_METHOD, "GET")
    parent_span.set_tag(ext.HTTP_STATUS_CODE, 200)
    parent_span.log_kv({"foo": "bar"})

    child_span = ot.tracer.start_span(operation_name="child", child_of=parent_span)
    child_span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_CLIENT)
    child_span.set_tag(ext.PEER_HOSTNAME, "localhost")
    child_span.set_tag(ext.HTTP_URL, "/python/simple/two")
    child_span.set_tag(ext.HTTP_METHOD, "POST")
    child_span.set_tag(ext.HTTP_STATUS_CODE, 204)
    child_span.set_baggage_item("someBaggage", "someValue")

    time.sleep(.45)
    child_span.finish()

    time.sleep(.55)
    parent_span.finish()

if __name__ == "__main__":
    main(sys.argv)
