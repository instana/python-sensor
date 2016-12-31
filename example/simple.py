import sys
import instana.sensor as s
import instana.options as o
import logging
import opentracing as ot
import instana.tracer
import time
import instana.data as d
import instana.http as h

def main(argv):
    instana.tracer.init(o.Options(service='python-simple',
                                log_level=logging.DEBUG))

    while (True):
        simple()

def simple():
    parent_span = ot.tracer.start_span(operation_name="parent")
    parent_span.log_kv({"type": h.HTTP_SERVER,
                        "data": d.Data(http=h.HttpData(host="localhost",
            			                               url="/python/simple/one",
            			                               status=200,
            			                               method="GET"))})
    child_span = ot.tracer.start_span(operation_name="child", child_of=parent_span)
    child_span.log_kv({"type": h.HTTP_CLIENT,
                       "data": d.Data(http=h.HttpData(host="localhost",
            		                                  url="/python/simple/two",
            		                                  status=204,
            		                                  method="POST"))})
    child_span.set_baggage_item("someBaggage", "someValue")
    time.sleep(.45)
    child_span.finish()
    time.sleep(.55)
    parent_span.finish()

if __name__ == "__main__":
    main(sys.argv)
