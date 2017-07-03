import os
import opentracing
import instana.tracer
os.environ["INSTANA_TEST"] = "true"

opentracing.global_tracer = instana.tracer.InstanaTracer()
